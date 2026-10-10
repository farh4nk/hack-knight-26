"""The camera on/off switch: releases the device, ends the Presage session, reports state."""

import asyncio
import sys
import time

import numpy as np
import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from cradleecho.camera import Camera
from cradleecho.classifier import SleepStateClassifier
from cradleecho.config import settings
from cradleecho.main import create_app
from cradleecho.sources.mock import MockVitalsSource
from cradleecho.sources.presage import PresageVitalsSource


class CountingCap:
    """Fake camera that tracks whether it is open (frames flow only while open)."""

    opened = 0
    released = 0

    def __init__(self) -> None:
        type(self).opened += 1
        self._open = True

    def isOpened(self) -> bool:
        return self._open

    def read(self):
        if not self._open:
            return False, None
        time.sleep(0.01)
        return True, np.zeros((480, 640, 3), dtype=np.uint8)

    def set(self, prop, val) -> None:
        pass

    def release(self) -> None:
        self._open = False
        type(self).released += 1


def wait_for(cond, timeout=3.0):
    end = time.time() + timeout
    while time.time() < end:
        if cond():
            return True
        time.sleep(0.02)
    return False


def test_turning_the_camera_off_releases_the_device_and_on_reopens_it(monkeypatch):
    CountingCap.opened = CountingCap.released = 0
    monkeypatch.setattr("cv2.VideoCapture", lambda x: CountingCap())
    cam = Camera(device="0", enabled=True)
    cam.start()
    try:
        assert wait_for(cam.is_live)
        assert CountingCap.opened == 1 and CountingCap.released == 0

        cam.set_enabled(False)
        assert wait_for(lambda: not cam.is_live())
        assert wait_for(lambda: CountingCap.released == 1), "device must be released when off"
        assert cam.get_latest_frame_jpeg() == cam._paused_jpeg
        assert cam.get_motion_index() == 0.0

        cam.set_enabled(True)
        assert wait_for(cam.is_live), "frames must flow again after turning it back on"
        assert CountingCap.opened == 2
    finally:
        cam.stop()


def test_camera_that_starts_off_never_opens_the_device(monkeypatch):
    CountingCap.opened = CountingCap.released = 0
    monkeypatch.setattr("cv2.VideoCapture", lambda x: CountingCap())
    cam = Camera(device="0", enabled=False)
    cam.start()
    try:
        time.sleep(0.4)
        assert CountingCap.opened == 0
        assert not cam.is_enabled() and not cam.is_live()
        assert cam.get_latest_frame_jpeg() == cam._paused_jpeg != cam._fallback_jpeg
    finally:
        cam.stop()


def test_api_toggle_reports_camera_off_and_clears_readings():
    camera = Camera(device="none")
    app = create_app(camera=camera, source=MockVitalsSource(seed=1), classifier=SleepStateClassifier())
    with TestClient(app) as client:
        assert client.get("/api/camera").json()["enabled"] is True
        assert client.get("/api/state").json()["camera"]["enabled"] is True

        r = client.post("/api/camera", json={"enabled": False})
        assert r.status_code == 200 and r.json()["enabled"] is False
        state = client.get("/api/state").json()
        assert state["camera"]["enabled"] is False
        assert state["state"] == "SIGNAL_UNSTABLE"
        assert state["vitals"] == {"brpm": 0.0, "bpm": 0.0, "confidence": 0.0}
        assert state["motion_index"] == 0.0

        client.post("/api/camera", json={"enabled": True})
        assert client.get("/api/state").json()["camera"]["enabled"] is True


def test_api_rejects_a_bad_toggle_body():
    camera = Camera(device="none")
    app = create_app(camera=camera, source=MockVitalsSource(seed=1), classifier=SleepStateClassifier())
    with TestClient(app) as client:
        assert client.post("/api/camera", json={"enabled": "maybe"}).status_code == 422
        assert client.post("/api/camera", json={}).status_code == 422


@pytest.fixture
def presage_key(monkeypatch):
    monkeypatch.setenv("PRESAGE_API_KEY", "fake_key_for_test")
    monkeypatch.setattr(settings, "presage_api_key", SecretStr("fake_key_for_test"))


@pytest.mark.asyncio
async def test_pausing_presage_ends_the_session_and_resuming_restarts_it(presage_key):
    """No bridge process while paused means no Presage credits are used."""
    source = PresageVitalsSource(cmd=[sys.executable, "presage_bridge/fake_bridge.py"])
    await source.start()
    try:
        for _ in range(60):
            if source.session_running and source.read().confidence > 0.8:
                break
            await asyncio.sleep(0.05)
        assert source.session_running

        source.set_paused(True)
        for _ in range(60):
            if not source.session_running:
                break
            await asyncio.sleep(0.05)
        assert not source.session_running, "pausing must end the Presage session"
        assert source.read().confidence == 0.0

        source.set_paused(False)
        for _ in range(100):
            if source.session_running and source.read().confidence > 0.8:
                break
            await asyncio.sleep(0.05)
        assert source.session_running and source.read().confidence > 0.8
    finally:
        await source.stop()


class AlwaysOpenGate:
    """A face gate that always sees a face: without the pause guard it would re-open Presage."""

    is_active = False
    reason = "ok"

    def __init__(self) -> None:
        self.updates = 0
        self.resets = 0

    def update(self, frame) -> bool:
        self.updates += 1
        self.is_active = True
        return True

    def reset(self) -> None:
        self.resets += 1
        self.is_active = False


@pytest.mark.asyncio
async def test_paused_presage_ignores_frames_even_if_the_gate_sees_a_face(presage_key):
    source = PresageVitalsSource(cmd=[sys.executable, "presage_bridge/fake_bridge.py", "--stdin", "64x48"])
    gate = AlwaysOpenGate()
    source.set_gate(gate)
    await source.start()
    try:
        source.set_paused(True)
        assert gate.resets == 1, "pausing re-arms the gate so resuming needs a fresh face detection"
        source.push_frame(np.zeros((48, 64, 3), dtype=np.uint8))
        assert gate.updates == 0, "the face gate must not even run while paused"
        assert not source.session_running

        source.set_paused(False)
        source.push_frame(np.zeros((48, 64, 3), dtype=np.uint8))
        assert gate.updates == 1, "frames are evaluated again after resuming"
    finally:
        await source.stop()
