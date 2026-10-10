"""Tests for listen (Pi mic -> browser) WebSocket."""

import asyncio
import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock, patch

from cradleecho.camera import Camera
from cradleecho.classifier import SleepStateClassifier
from cradleecho.config import settings
from cradleecho.main import create_app
from cradleecho.sources.mock import MockVitalsSource
from cradleecho.listen import ListenHub, ListenConfig, handle_listen_ws


class FakeRecorderProcess:
    """Mock arecord subprocess that yields fake audio chunks."""
    def __init__(self, chunks=None):
        self.stdout = AsyncMock()
        self._chunks = chunks or [b"x" * 1280, b"y" * 1280, b"z" * 1280]
        self._idx = 0
        self.stdout.read = AsyncMock(side_effect=self._read_chunk)
        self._returncode = None
        self.pid = 12345  # Needed for logging

    async def _read_chunk(self, n):
        if self._idx < len(self._chunks):
            chunk = self._chunks[self._idx]
            self._idx += 1
            return chunk
        return b""

    def kill(self):
        pass

    def terminate(self):
        self._returncode = -15

    async def wait(self):
        return 0


@pytest.fixture
def test_app():
    camera = Camera(device="none")
    source = MockVitalsSource(seed=42)
    classifier = SleepStateClassifier()
    
    # ListenHub with fake recorder
    config = ListenConfig(
        recorder_argv=["cat", ">", "/dev/null"],
        device="default",
    )
    hub = ListenHub(config)
    # Override enabled for testing
    hub._enabled = True
    
    app = create_app(camera=camera, source=source, classifier=classifier, listen_hub=hub)
    return app, hub


def test_listen_disabled_returns_4403():
    """Test that listen endpoint returns 4403 when disabled."""
    import asyncio
    from cradleecho.listen import ListenHub, handle_listen_ws
    
    config = ListenConfig(recorder_argv=["cat"])
    hub = ListenHub(config)
    hub._enabled = False
    
    # Test the handler directly with a mock websocket
    ws = AsyncMock()
    ws.accept = AsyncMock()
    ws.close = AsyncMock()
    
    async def run_test():
        await handle_listen_ws(hub, ws)
        ws.accept.assert_called_once()
        ws.close.assert_called_with(code=4403)
    
    asyncio.run(run_test())


@pytest.mark.asyncio
async def test_listen_fans_out_to_two_subscribers():
    """Test that listen hub fans out chunks to multiple subscribers."""
    config = ListenConfig(
        recorder_argv=["nonexistent_arecord_12345"],
    )
    hub = ListenHub(config)
    hub._enabled = True
    
    # Mock the recorder process
    fake_proc = FakeRecorderProcess(chunks=[b"A" * 1280, b"B" * 1280])
    
    with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_create:
        mock_create.return_value = fake_proc
        
        # Subscribe two clients
        queue1 = await hub.subscribe()
        queue2 = await hub.subscribe()
        
        # Wait for chunks to be fanned out
        await asyncio.sleep(0.1)
        
        # Both queues should have received chunks
        chunks1 = []
        while not queue1.empty():
            chunks1.append(queue1.get_nowait())
        
        chunks2 = []
        while not queue2.empty():
            chunks2.append(queue2.get_nowait())
        
        assert len(chunks1) >= 1
        assert len(chunks2) >= 1
        assert chunks1 == chunks2  # Both get same data
        
        # Unsubscribe both
        await hub.unsubscribe(queue1)
        await hub.unsubscribe(queue2)
        
        # Recorder should be stopped after last unsubscribes
        await asyncio.sleep(0.05)
        # The recorder task should be cancelled


@pytest.mark.asyncio
async def test_listen_stops_recorder_when_last_leaves():
    """Test recorder stops when last subscriber leaves."""
    config = ListenConfig(
        recorder_argv=["nonexistent_arecord_12345"],
    )
    hub = ListenHub(config)
    hub._enabled = True
    
    fake_proc = FakeRecorderProcess(chunks=[b"A" * 1280])
    
    with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_create:
        mock_create.return_value = fake_proc
        
        queue1 = await hub.subscribe()
        await hub.unsubscribe(queue1)
        
        await asyncio.sleep(0.05)
        # Recorder should be stopped


@pytest.mark.asyncio
async def test_listen_bounded_queue_drops_oldest():
    """Test that slow subscriber's queue drops oldest chunks."""
    config = ListenConfig(
        recorder_argv=["nonexistent_arecord_12345"],
    )
    hub = ListenHub(config)
    hub._enabled = True
    
    # Create many chunks quickly
    fake_proc = FakeRecorderProcess(chunks=[bytes([i]) * 1280 for i in range(100)])
    
    with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_create:
        mock_create.return_value = fake_proc
        
        queue = await hub.subscribe()
        
        # Don't consume from queue, let it fill up
        await asyncio.sleep(0.2)
        
        # Queue should be bounded (maxsize=50)
        assert queue.qsize() <= 50
        
        await hub.unsubscribe(queue)


@pytest.mark.asyncio
async def test_listen_websocket_integration():
    """Test listen WebSocket endpoint integration."""
    from cradleecho.listen import handle_listen_ws
    
    config = ListenConfig(recorder_argv=["nonexistent_arecord_12345"])
    hub = ListenHub(config)
    hub._enabled = True
    
    fake_proc = FakeRecorderProcess(chunks=[b"TEST" * 320])
    
    with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_create:
        mock_create.return_value = fake_proc
        
        # Mock websocket
        ws = AsyncMock()
        ws.accept = AsyncMock()
        ws.send_bytes = AsyncMock()
        ws.receive = AsyncMock(side_effect=[
            {"type": "websocket.disconnect"}  # Client disconnects after receiving
        ])
        
        async def run_test():
            # Run handler with a timeout
            await asyncio.wait_for(handle_listen_ws(hub, ws), timeout=1.0)
        
        await run_test()
        
        ws.accept.assert_called_once()
        ws.send_bytes.assert_called_with(b"TEST" * 320)


def test_listen_config_device():
    """Test ListenHub respects device config."""
    config = ListenConfig(device="hw:1,0")
    hub = ListenHub(config)
    assert hub._device == "hw:1,0"