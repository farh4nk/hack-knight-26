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
