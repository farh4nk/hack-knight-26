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
    
    assert set(payload.keys()) == {"timestamp", "state", "vitals", "motion_index"}
    assert set(payload["vitals"].keys()) == {"brpm", "bpm", "confidence"}
    
    assert re.match(r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$", payload["timestamp"])
    assert payload["state"] in VALID_STATES


def test_contract_api_state_mock():
    camera = Camera(device="none")
    source = MockVitalsSource(seed=42)
    classifier = SleepStateClassifier()
    app = create_app(camera=camera, source=source, classifier=classifier)
    
    with TestClient(app) as client:
        response = client.get("/api/state")
        assert response.status_code == 200
        payload = response.json()
        
        assert set(payload.keys()) == {"timestamp", "state", "vitals", "motion_index"}
        assert set(payload["vitals"].keys()) == {"brpm", "bpm", "confidence"}
        assert re.match(r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$", payload["timestamp"])
        assert payload["state"] in VALID_STATES


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
        
        assert set(payload.keys()) == {"timestamp", "state", "vitals", "motion_index"}
        assert set(payload["vitals"].keys()) == {"brpm", "bpm", "confidence"}
        assert re.match(r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$", payload["timestamp"])
        assert payload["state"] in VALID_STATES
