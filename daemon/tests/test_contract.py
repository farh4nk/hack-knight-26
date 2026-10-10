import re
import asyncio
from datetime import datetime
import pytest

from cradleecho.telemetry import format_telemetry_payload
from cradleecho.sources.mock import MockVitalsSource
from cradleecho.sources.base import Reading
from cradleecho.classifier import VALID_STATES
from fastapi.testclient import TestClient
from cradleecho.main import create_app
from cradleecho.camera import Camera
from cradleecho.sources.presage import PresageVitalsSource
from cradleecho.classifier import SleepStateClassifier


def test_contract_format_telemetry_payload():
    payload = format_telemetry_payload(
        state="ASLEEP",
        reading=Reading(brpm=24.0, bpm=120.0, confidence=0.95, motion_index=0.1),
        motion_index=0.1
    )
    
    assert set(payload.keys()) == {"timestamp", "state", "vitals", "motion_index", "camera"}
    assert set(payload["vitals"].keys()) == {"brpm", "bpm", "confidence"}
    assert set(payload["camera"].keys()) == {"live", "gate", "framing", "sdk_code", "sdk_hint", "night_vision", "enhancing"}
    
    assert re.match(r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$", payload["timestamp"])
    assert payload["state"] in VALID_STATES
    assert payload["camera"]["gate"] == "DISABLED"
    assert payload["camera"]["framing"] == "UNKNOWN"
    assert payload["camera"]["live"] is False
    assert payload["camera"]["night_vision"] == "OFF"
    assert payload["camera"]["enhancing"] is False


def test_contract_api_state_mock():
    camera = Camera(device="none")
    source = MockVitalsSource(seed=42)
    classifier = SleepStateClassifier()
    app = create_app(camera=camera, source=source, classifier=classifier)
    
    with TestClient(app) as client:
        response = client.get("/api/state")
        assert response.status_code == 200
        payload = response.json()
        
        assert set(payload.keys()) == {"timestamp", "state", "vitals", "motion_index", "camera"}
        assert set(payload["vitals"].keys()) == {"brpm", "bpm", "confidence"}
        assert set(payload["camera"].keys()) == {"live", "gate", "framing", "sdk_code", "sdk_hint", "night_vision", "enhancing"}
        assert re.match(r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$", payload["timestamp"])
        assert payload["state"] in VALID_STATES
        assert payload["camera"]["live"] is False
        assert payload["camera"]["gate"] == "DISABLED"
        assert payload["camera"]["framing"] == "UNKNOWN"
        assert payload["camera"]["night_vision"] == "AUTO"
        assert payload["camera"]["enhancing"] is False


def test_contract_api_state_stale_presage():
    class StalePresageSource(PresageVitalsSource):
        def __init__(self):
            # Bypass parent init
            pass
        
        async def start(self):
            pass
            
        async def stop(self):
            pass
            
        def read(self):
            return Reading(brpm=0.0, bpm=0.0, confidence=0.0, motion_index=0.0)

    camera = Camera(device="none")
    source = StalePresageSource()
    classifier = SleepStateClassifier()
    app = create_app(camera=camera, source=source, classifier=classifier)
    
    with TestClient(app) as client:
        response = client.get("/api/state")
        assert response.status_code == 200
        payload = response.json()
        
        assert set(payload.keys()) == {"timestamp", "state", "vitals", "motion_index", "camera"}
        assert set(payload["vitals"].keys()) == {"brpm", "bpm", "confidence"}
        assert set(payload["camera"].keys()) == {"live", "gate", "framing", "sdk_code", "sdk_hint", "night_vision", "enhancing"}
        assert re.match(r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$", payload["timestamp"])
        assert payload["state"] in VALID_STATES
        assert payload["camera"]["sdk_code"] is None
        assert payload["camera"]["sdk_hint"] is None
        assert payload["camera"]["night_vision"] == "AUTO"
        assert payload["camera"]["enhancing"] is False

def test_contract_camera_fields():
    from cradleecho.sources.presage import PresageVitalsSource
    from cradleecho.facegate import FaceGate

    # test various gate reasons mapped
    class FakeGate:
        def __init__(self, active, reason):
            self.is_active = active
            self.reason = reason

    class StubSource:
        def __init__(self, gate, code, hint, running):
            self.gate = gate
            self._validation_code = code
            self._validation_hint = hint
            self.session_running = running
        
        @property
        def validation_code(self): return self._validation_code
        @property
        def raw_validation_hint(self): return self._validation_hint

    class FakeCamera:
        def is_live(self): return True

    cam = FakeCamera()
    
    # 1. ok -> OPEN, OK
    src1 = StubSource(FakeGate(True, "ok"), "kFaceLow", "Move up", True)
    payload1 = format_telemetry_payload("ASLEEP", Reading(0.0, 0.0, 0.0, 0.0), 0.0, camera=cam, source=src1)
    assert payload1["camera"]["live"] is True
    assert payload1["camera"]["gate"] == "OPEN"
    assert payload1["camera"]["framing"] == "OK"
    assert payload1["camera"]["sdk_code"] == "kFaceLow"
    assert payload1["camera"]["sdk_hint"] == "Move up"

    # 2. no_face -> CLOSED, NO_FACE
    src2 = StubSource(FakeGate(False, "no_face"), None, None, False)
    payload2 = format_telemetry_payload("ASLEEP", Reading(0.0, 0.0, 0.0, 0.0), 0.0, camera=cam, source=src2)
    assert payload2["camera"]["gate"] == "CLOSED"
    assert payload2["camera"]["framing"] == "NO_FACE"
    assert payload2["camera"]["sdk_code"] is None
    assert payload2["camera"]["sdk_hint"] is None

    # 3. other mappings
    for reason, expected in [
        ("multiple_faces", "MULTIPLE_FACES"),
        ("too_small", "TOO_SMALL"),
        ("off_center", "OFF_CENTER"),
        ("no_chest_room", "NO_CHEST_ROOM"),
        ("random_unseen", "UNKNOWN"),
    ]:
        src = StubSource(FakeGate(True, reason), None, None, True)
        payload = format_telemetry_payload("ASLEEP", Reading(0.0, 0.0, 0.0, 0.0), 0.0, camera=cam, source=src)
        assert payload["camera"]["framing"] == expected

