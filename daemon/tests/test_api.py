"""API and integration tests for CradleEcho edge daemon."""

import asyncio
from datetime import datetime
import json
import os
import sys
import pytest
from fastapi.testclient import TestClient

from cradleecho.camera import Camera
from cradleecho.classifier import SleepStateClassifier, VALID_STATES
from cradleecho.main import create_app
from cradleecho.sources.mock import MockVitalsSource
from cradleecho.sources.presage import PresageVitalsSource
from cradleecho.telemetry import TelemetryHub


@pytest.fixture
def test_app():
    """Create test FastAPI application with synthetic camera feed."""
    camera = Camera(device="none")
    source = MockVitalsSource(seed=42)
    classifier = SleepStateClassifier()
    app = create_app(camera=camera, source=source, classifier=classifier)
    return app


def test_healthz(test_app):
    with TestClient(test_app) as client:
        response = client.get("/healthz")
        assert response.status_code == 200
        assert response.json() == {"status": "ok", "source": "mock"}


def test_api_state_schema(test_app):
    with TestClient(test_app) as client:
        response = client.get("/api/state")
        assert response.status_code == 200
        data = response.json()

        # Validate AGENTS.md contract
        assert "timestamp" in data
        assert data["timestamp"].endswith("Z")
        # Validate timestamp parseable
        datetime.fromisoformat(data["timestamp"].replace("Z", "+00:00"))

        assert "state" in data
        assert data["state"] in VALID_STATES

        assert "vitals" in data
        vitals = data["vitals"]
        assert "brpm" in vitals and isinstance(vitals["brpm"], (int, float))
        assert "bpm" in vitals and isinstance(vitals["bpm"], (int, float))
        assert "confidence" in vitals and isinstance(vitals["confidence"], (int, float))

        assert "motion_index" in data
        assert isinstance(data["motion_index"], (int, float))


def test_simulate_restless(test_app):
    with TestClient(test_app) as client:
        # Trigger simulate-restless
        response = client.post("/api/simulate-restless", json={"seconds": 15.0})
        assert response.status_code == 200
        body = response.json()
        assert "forced_until" in body
        assert body["forced_until"].endswith("Z")

        # Telemetry state should immediately reflect RESTLESS
        state_resp = client.get("/api/state")
        assert state_resp.status_code == 200
        assert state_resp.json()["state"] == "RESTLESS"


def test_source_toggle(test_app):
    with TestClient(test_app) as client:
        resp = client.get("/api/source")
        assert resp.status_code == 200
        assert "source" in resp.json()

        # Switch to real
        resp = client.post("/api/source", json={"source": "real"})
        assert resp.status_code == 200
        assert resp.json()["source"] == "real"
        assert resp.json()["mode"] == "REALTIME"

        # Switch back to mock
        resp = client.post("/api/source", json={"source": "mock"})
        assert resp.status_code == 200
        assert resp.json()["source"] == "mock"
        assert resp.json()["mode"] == "SIMULATED"


def test_video_feed_mjpeg(test_app):
    with TestClient(test_app) as client:
        response = client.get("/video_feed?limit=1")
        assert response.status_code == 200
        content_type = response.headers.get("content-type", "")
        assert "multipart/x-mixed-replace" in content_type
        assert "boundary=frame" in content_type

        assert b"--frame" in response.content
        assert b"Content-Type: image/jpeg" in response.content
        assert b"\xff\xd8" in response.content


def test_websocket_telemetry(test_app):
    with TestClient(test_app) as client:
        with client.websocket_connect("/ws/telemetry") as ws:
            # Immediately upon connection, hub sends initial state
            msg = ws.receive_text()
            payload = json.loads(msg)

            assert "timestamp" in payload
            assert payload["timestamp"].endswith("Z")
            assert payload["state"] in VALID_STATES
            assert "vitals" in payload
            assert "brpm" in payload["vitals"]
            assert "bpm" in payload["vitals"]
            assert "confidence" in payload["vitals"]
            assert "motion_index" in payload


@pytest.mark.asyncio
async def test_presage_source_and_fake_bridge():
    """Verify Presage subprocess adapter reading NDJSON from fake_bridge."""
    fake_bridge_path = os.path.join(
        os.path.dirname(__file__), "..", "presage_bridge", "fake_bridge.py"
    )
    cmd = [sys.executable, fake_bridge_path]

    source = PresageVitalsSource(cmd=cmd, stale_timeout_s=1.5)
    await source.start()

    try:
        # Wait up to 2 seconds for first NDJSON line to be read
        reading = None
        for _ in range(20):
            await asyncio.sleep(0.1)
            r = source.read()
            if r.confidence > 0.0:
                reading = r
                break

        assert reading is not None, "Failed to read non-zero reading from fake bridge"
        assert 20.0 <= reading.brpm <= 30.0
        assert 110.0 <= reading.bpm <= 130.0
        assert reading.confidence >= 0.80

        # Test stale awareness: if timeout elapses without messages, confidence drops to 0.0
        # Stop source to stop receiving messages
        await source.stop()
        # Wait until stale timeout passes
        await asyncio.sleep(1.6)
        stale_reading = source.read()
        assert stale_reading.confidence == 0.0
    finally:
        await source.stop()

def test_video_feed_debug(test_app):
    cam = test_app.state.camera
    assert getattr(cam, "_debug_viewers", 0) == 0
    with TestClient(test_app) as client:
        response = client.get("/video_feed/debug?limit=1")
        assert response.status_code == 200
        content_type = response.headers.get("content-type", "")
        assert "multipart/x-mixed-replace" in content_type
        assert b"--frame" in response.content
        assert b"\xff\xd8" in response.content
    assert cam._debug_viewers == 0

def test_camera_debug_slot():
    from cradleecho.camera import Camera
    import time
    cam = Camera(device="none")
    # For dummy source, _capture_loop doesn't grab real frames. 
    # But let's just test that without viewers we have no debug jpeg, and with viewers we do?
    # Wait, for dummy device, frame is None, so it always yields the fallback frame.
    pass

def test_camera_debug_slot(monkeypatch):
    from cradleecho.camera import Camera
    import time
    import numpy as np
    
    class FakeCap:
        def isOpened(self): return True
        def read(self):
            return True, np.zeros((480, 640, 3), dtype=np.uint8)
        def set(self, prop, val): pass
        def release(self): pass
        
    monkeypatch.setattr("cv2.VideoCapture", lambda x: FakeCap())
    
    cam = Camera(device="0")
    cam.set_overlay(lambda f: None)
    cam.start()
    try:
        assert cam._debug_viewers == 0
        time.sleep(0.2)
        assert cam.get_latest_debug_jpeg() == cam._latest_jpeg
        assert cam._latest_debug_jpeg == b""
        
        cam.acquire_debug()
        time.sleep(0.2)
        assert len(cam._latest_debug_jpeg) > 0
        
        cam.release_debug()
        time.sleep(0.2)
        assert cam._latest_debug_jpeg == b""
    finally:
        cam.stop()


def test_preview_is_encoded_slowly_without_viewers_and_fast_with_one(monkeypatch):
    """JPEG encoding is CPU the Presage bridge needs: ~1/s idle, stream_fps while watched."""
    import time

    import numpy as np

    from cradleecho.camera import Camera

    class FakeCap:
        def isOpened(self):
            return True

        def read(self):
            time.sleep(1 / 60)
            return True, np.zeros((480, 640, 3), dtype=np.uint8)

        def set(self, prop, val):
            pass

        def release(self):
            pass

    monkeypatch.setattr("cv2.VideoCapture", lambda x: FakeCap())
    cam = Camera(device="0")
    cam.start()
    try:
        time.sleep(0.3)
        idle_start = cam.get_frame_seq()
        time.sleep(1.0)
        idle = cam.get_frame_seq() - idle_start
        assert idle <= 3, idle

        cam.acquire_viewer()
        time.sleep(0.3)
        watched_start = cam.get_frame_seq()
        time.sleep(1.0)
        watched = cam.get_frame_seq() - watched_start
        assert watched >= 10, watched
        cam.release_viewer()
    finally:
        cam.stop()
