import asyncio
import sys
import time

import pytest
from pydantic import SecretStr

from cradleecho.config import settings
from cradleecho.sources.presage import PresageVitalsSource


@pytest.fixture(autouse=True)
def mock_env_vars(monkeypatch):
    monkeypatch.setenv("PRESAGE_API_KEY", "fake_key_for_test")
    monkeypatch.setattr(settings, "presage_api_key", SecretStr("fake_key_for_test"))

@pytest.mark.asyncio
async def test_presage_source_with_fake_bridge():
    # Use the fake bridge which should emit valid readings
    source = PresageVitalsSource(cmd=[sys.executable, "presage_bridge/fake_bridge.py"])
    await source.start()
    
    try:
        # Wait up to 2 seconds for a valid reading
        start_time = time.time()
        reading = None
        while time.time() - start_time < 2.0:
            reading = source.read()
            if reading.confidence > 0.8:
                break
            await asyncio.sleep(0.1)
        
        assert reading is not None
        assert reading.confidence > 0.8
        assert reading.brpm > 0.0
        assert reading.bpm > 0.0
    finally:
        await source.stop()
        
@pytest.mark.asyncio
async def test_presage_source_stale_timeout():
    # A script that prints one valid JSON reading and then sleeps forever
    inline_script = (
        "import time, sys\n"
        "print('{\"t\": ' + str(time.time()) + ', \"brpm\": 25, \"bpm\": 110, \"confidence\": 0.9}')\n"
        "sys.stdout.flush()\n"
        "time.sleep(10)\n"
    )
    
    source = PresageVitalsSource(
        cmd=[sys.executable, "-c", inline_script],
        stale_timeout_s=0.5
    )
    await source.start()
    
    try:
        # Wait for the first reading to be parsed
        start_time = time.time()
        reading = None
        while time.time() - start_time < 2.0:
            reading = source.read()
            if reading.confidence == 0.9:
                break
            await asyncio.sleep(0.1)
            
        assert reading is not None
        assert reading.confidence == 0.9
        
        # Wait for it to go stale (stale_timeout_s = 0.5)
        await asyncio.sleep(0.6)
        
        stale_reading = source.read()
        assert stale_reading.confidence == 0.0
    finally:
        await source.stop()
        
@pytest.mark.asyncio
async def test_presage_source_malformed_json():
    # A script that prints non-JSON, then valid JSON
    inline_script = (
        "import time, sys\n"
        "print('this is not json')\n"
        "print('{\"t\": ' + str(time.time()) + ', \"brpm\": 25, \"bpm\": 110, \"confidence\": 0.85}')\n"
        "sys.stdout.flush()\n"
        "time.sleep(10)\n"
    )
    
    source = PresageVitalsSource(
        cmd=[sys.executable, "-c", inline_script],
        stale_timeout_s=3.0
    )
    await source.start()
    
    try:
        start_time = time.time()
        reading = None
        while time.time() - start_time < 2.0:
            reading = source.read()
            if reading.confidence == 0.85:
                break
            await asyncio.sleep(0.1)
            
        # If it didn't crash and we got the reading, success
        assert reading is not None
        assert reading.confidence == 0.85
    finally:
        await source.stop()

@pytest.mark.asyncio
async def test_presage_source_stop_terminates_child():
    inline_script = (
        "import time\n"
        "while True: time.sleep(0.1)\n"
    )
    
    source = PresageVitalsSource(cmd=[sys.executable, "-c", inline_script])
    await source.start()
    
    # Wait for the worker to spawn the subprocess
    start_time = time.time()
    while source._proc is None and time.time() - start_time < 2.0:
        await asyncio.sleep(0.05)
        
    assert source._proc is not None
    assert source._proc.returncode is None  # Still running
    
    await source.stop()
    
    assert source._proc is None
    assert source._running is False

@pytest.mark.asyncio
async def test_presage_source_passes_api_key(monkeypatch):
    monkeypatch.setattr(settings, "presage_api_key", SecretStr("test_secret_123"))
    inline_script = (
        "import os, sys, time\n"
        "key = os.environ.get('PRESAGE_API_KEY')\n"
        "if key == 'test_secret_123':\n"
        "    print('{\"t\": ' + str(time.time()) + ', \"brpm\": 25, \"bpm\": 110, \"confidence\": 0.99}')\n"
        "    sys.stdout.flush()\n"
        "time.sleep(10)\n"
    )
    source = PresageVitalsSource(cmd=[sys.executable, "-c", inline_script])
    await source.start()
    try:
        start_time = time.time()
        reading = None
        while time.time() - start_time < 2.0:
            reading = source.read()
            if reading.confidence == 0.99:
                break
            await asyncio.sleep(0.1)
        assert reading is not None
        assert reading.confidence == 0.99
    finally:
        await source.stop()


@pytest.mark.asyncio
async def test_push_frame_reaches_bridge_stdin():
    import numpy as np

    source = PresageVitalsSource(
        cmd=[sys.executable, "presage_bridge/fake_bridge.py", "--stdin", "32x24"],
        max_fps=1000,
    )
    assert source.wants_frames
    await source.start()
    try:
        # No frames yet: the fake bridge stays silent, so the source reads as unstable.
        await asyncio.sleep(0.3)
        assert source.read().confidence == 0.0

        # Wrong-sized frames are resized to the bridge's WxH before being written.
        frame = np.zeros((48, 64, 3), dtype=np.uint8)
        reading = source.read()
        deadline = time.time() + 3.0
        while time.time() < deadline and reading.bpm < 3:
            await asyncio.to_thread(source.push_frame, frame)
            await asyncio.sleep(0.05)
            reading = source.read()

        assert reading.bpm >= 3  # bridge counted the frames we piped in
        assert reading.confidence > 0.8
    finally:
        await source.stop()


@pytest.mark.asyncio
async def test_push_frame_is_noop_without_stdin_mode():
    import numpy as np

    source = PresageVitalsSource(cmd=[sys.executable, "presage_bridge/fake_bridge.py"])
    assert not source.wants_frames
    await source.start()
    try:
        source.push_frame(np.zeros((24, 32, 3), dtype=np.uint8))  # must not raise
    finally:
        await source.stop()


@pytest.mark.asyncio
async def test_push_frame_throttles():
    import numpy as np

    source = PresageVitalsSource(
        cmd=[sys.executable, "presage_bridge/fake_bridge.py", "--stdin", "32x24"],
        max_fps=1,
    )
    await source.start()
    try:
        frame = np.zeros((24, 32, 3), dtype=np.uint8)
        for _ in range(10):
            await asyncio.to_thread(source.push_frame, frame)
        await asyncio.sleep(0.5)
        assert source.read().bpm <= 1  # only one frame admitted at 1 fps
    finally:
        await source.stop()

class StubGate:
    def __init__(self):
        self.is_active = False

    def update(self, frame):
        return self.is_active

@pytest.mark.asyncio
async def test_presage_source_with_gate(tmp_path, monkeypatch):
    import numpy as np

    # A counter file to track bridge spawns
    counter_file = tmp_path / "spawn_count.txt"
    counter_file.write_text("0")

    inline_script = f"""
import sys, time, json
with open({repr(str(counter_file))}, 'r+') as f:
    val = int(f.read())
    f.seek(0)
    f.write(str(val + 1))
    f.truncate()

while True:
    print(json.dumps({{"t": time.time(), "brpm": 25, "bpm": 110, "confidence": 0.99}}))
    sys.stdout.flush()
    time.sleep(0.5)
"""

    gate = StubGate()
    gate.is_active = False # Gate starts inactive

    source = PresageVitalsSource(
        cmd=[sys.executable, "-c", inline_script],
        stale_timeout_s=1.0,
    )
    # fake wants_frames
    source._frame_size = (32, 24)
    source.set_gate(gate)
    
    await source.start()

    try:
        # Gate is inactive, so bridge should NOT be spawned
        await asyncio.sleep(0.5)
        assert counter_file.read_text() == "0"
        
        # We push a frame, gate still inactive
        frame = np.zeros((24, 32, 3), dtype=np.uint8)
        await asyncio.to_thread(source.push_frame, frame)
        await asyncio.sleep(0.5)
        assert counter_file.read_text() == "0"

        # Gate becomes active
        gate.is_active = True
        await asyncio.to_thread(source.push_frame, frame)
        
        # Bridge should be spawned now
        start_time = time.time()
        reading = None
        while time.time() - start_time < 3.0:
            reading = source.read()
            if reading.confidence == 0.99:
                break
            await asyncio.sleep(0.1)
            
        assert counter_file.read_text() == "1"
        assert reading is not None
        assert reading.confidence == 0.99
        
        # Gate becomes inactive again
        gate.is_active = False
        await asyncio.to_thread(source.push_frame, frame)
        
        # Read should go to 0.0 quickly (immediate)
        # Wait a small bit for thread to process
        await asyncio.sleep(0.1)
        reading = source.read()
        assert reading.confidence == 0.0

        # Wait to ensure it didn't respawn
        await asyncio.sleep(1.0)
        assert counter_file.read_text() == "1"

        # Gate becomes active again -> respawn
        gate.is_active = True
        await asyncio.to_thread(source.push_frame, frame)
        
        start_time = time.time()
        while time.time() - start_time < 3.0:
            reading = source.read()
            if reading.confidence == 0.99:
                break
            await asyncio.sleep(0.1)

        assert counter_file.read_text() == "2"
        assert reading.confidence == 0.99
        
    finally:
        await source.stop()

@pytest.mark.asyncio
async def test_presage_source_validation_hint():
    inline_script = (
        "import time, sys\n"
        "print('{\"t\": ' + str(time.time()) + ', \"validation\": \"kFaceTooLow\", \"hint\": \"Move up.\"}')\n"
        "sys.stdout.flush()\n"
        "time.sleep(0.1)\n"
        "print('{\"t\": ' + str(time.time()) + ', \"brpm\": 25, \"bpm\": 110, \"confidence\": 0.95}')\n"
        "sys.stdout.flush()\n"
        "time.sleep(10)\n"
    )
    
    source = PresageVitalsSource(
        cmd=[sys.executable, "-c", inline_script],
        stale_timeout_s=3.0
    )
    await source.start()
    
    try:
        start_time = time.time()
        reading = None
        hint = ""
        while time.time() - start_time < 2.0:
            reading = source.read()
            hint = source.validation_hint
            if reading.confidence == 0.95 and "kFaceTooLow" in hint:
                break
            await asyncio.sleep(0.1)
            
        assert reading is not None
        assert reading.confidence == 0.95
        assert reading.brpm == 25.0
        assert "kFaceTooLow: Move up." in hint
    finally:
        await source.stop()
        
    assert source.validation_hint == ""
