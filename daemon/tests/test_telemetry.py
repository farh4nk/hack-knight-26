import asyncio
import pytest

from cradleecho.classifier import SleepStateClassifier
from cradleecho.sources.mock import MockVitalsSource
from cradleecho.telemetry import TelemetryHub


class StubCamera:
    def __init__(self, live: bool, brightness: float):
        self._live = live
        self._brightness = brightness
        
    def get_motion_index(self):
        return 0.1

    def get_brightness(self):
        return self._brightness

    def is_live(self):
        return self._live


@pytest.mark.asyncio
async def test_seeded_payload():
    camera = StubCamera(False, 100)
    source = MockVitalsSource()
    classifier = SleepStateClassifier()
    hub = TelemetryHub(camera=camera, source=source, classifier=classifier)
    
    payload = hub.get_latest_payload()
    assert payload["state"] == "SIGNAL_UNSTABLE"
    assert payload["vitals"]["brpm"] == 0.0
    assert payload["vitals"]["bpm"] == 0.0
    assert payload["vitals"]["confidence"] == 0.0
    assert payload["motion_index"] == 0.0


@pytest.mark.asyncio
async def test_force_unstable():
    camera = StubCamera(False, 100)
    source = MockVitalsSource()
    classifier = SleepStateClassifier()
    hub = TelemetryHub(camera=camera, source=source, classifier=classifier)
    
    hub.force_unstable(seconds=5.0)
    payload = await hub.step()
    assert payload["state"] == "SIGNAL_UNSTABLE"
    assert payload["vitals"]["confidence"] == 0.0


@pytest.mark.asyncio
async def test_dark_frame_gate():
    camera_dark = StubCamera(True, 10)
    source = MockVitalsSource()
    classifier = SleepStateClassifier()
    hub_dark = TelemetryHub(camera=camera_dark, source=source, classifier=classifier)
    
    payload = await hub_dark.step()
    assert payload["state"] == "SIGNAL_UNSTABLE"
    assert payload["vitals"]["confidence"] == 0.0

    camera_bright = StubCamera(True, 100)
    hub_bright = TelemetryHub(camera=camera_bright, source=source, classifier=classifier)
    
    payload2 = await hub_bright.step()
    assert payload2["vitals"]["confidence"] > 0.0


class FakeWS:
    def __init__(self, behavior: str):
        self.behavior = behavior
        self.received = False
        
    async def send_text(self, data: str):
        if self.behavior == "raise":
            raise Exception("dead client")
        elif self.behavior == "hang":
            await asyncio.sleep(5)
            self.received = True
        else:
            self.received = True


@pytest.mark.asyncio
async def test_broadcast_drops_clients():
    hub = TelemetryHub(camera=StubCamera(False, 100), source=MockVitalsSource(), classifier=SleepStateClassifier())
    ws_good = FakeWS("good")
    ws_raise = FakeWS("raise")
    ws_hang = FakeWS("hang")
    
    hub._clients.update([ws_good, ws_raise, ws_hang])
    
    await hub.broadcast({"test": "data"})
    
    assert ws_good.received is True
    assert ws_raise.received is False
    assert ws_hang.received is False
    assert ws_good in hub._clients
    assert ws_raise not in hub._clients
    assert ws_hang not in hub._clients


@pytest.mark.asyncio
async def test_loop_rate():
    hub = TelemetryHub(
        camera=StubCamera(False, 100),
        source=MockVitalsSource(),
        classifier=SleepStateClassifier(),
        interval_s=0.05
    )
    
    step_count = 0
    original_step = hub.step
    
    async def _mock_step():
        nonlocal step_count
        step_count += 1
        await original_step()
        
    hub.step = _mock_step
    
    await hub.start()
    await asyncio.sleep(0.5)
    await hub.stop()
    
    assert 7 <= step_count <= 13
