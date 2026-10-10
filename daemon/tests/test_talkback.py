"""Tests for talkback (parent -> Pi speaker) WebSocket."""

import asyncio
import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock, patch

from cradleecho.camera import Camera
from cradleecho.classifier import SleepStateClassifier
from cradleecho.main import create_app
from cradleecho.sources.mock import MockVitalsSource
from cradleecho.talkback import TalkbackManager, TalkbackConfig, TalkbackSession


class FakePlayerProcess:
    """Mock subprocess that captures written data."""
    def __init__(self):
        self.stdin = AsyncMock()
        self.stdin.write = AsyncMock()
        self.stdin.drain = AsyncMock()
        self.stdin.close = AsyncMock()
        self._returncode = None
        self._wait_called = False
        self.pid = 12345  # Needed for logging

    async def wait(self):
        self._wait_called = True
        return 0

    def kill(self):
        pass

    def terminate(self):
        self._returncode = -15


@pytest.fixture
def test_app(request):
    timeout_s = getattr(request, "param", 60.0)
    camera = Camera(device="none")
    source = MockVitalsSource(seed=42)
    classifier = SleepStateClassifier()
    
    config = TalkbackConfig(
        player_argv=["python", "-c", "import sys; sys.stdin.buffer.read()"],
        session_timeout_s=timeout_s,
    )
    manager = TalkbackManager(config)
    app = create_app(camera=camera, source=source, classifier=classifier, talkback_manager=manager)
    return app, manager


def test_talkback_single_connection_writes_bytes(test_app):
    """Test that a single talkback connection can write bytes to the player."""
    app, manager = test_app
    
    fake_proc = FakePlayerProcess()
    
    with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_create:
        mock_create.return_value = fake_proc
        
        with TestClient(app) as client:
            with client.websocket_connect("/ws/talk") as ws:
                test_data = b"x" * 320
                ws.send_bytes(test_data)
                import time
                time.sleep(0.05)
    
    mock_create.assert_called_once()
    fake_proc.stdin.write.assert_called()
    fake_proc.stdin.drain.assert_called()


def test_talkback_second_connection_rejected_4409(test_app):
    """A second concurrent talker is closed with code 4409; the first keeps its session."""
    app, manager = test_app

    with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_create:
        mock_create.return_value = FakePlayerProcess()

        with TestClient(app) as client:
            with client.websocket_connect("/ws/talk") as ws1:
                ws1.send_bytes(b"\x00" * 320)
                with client.websocket_connect("/ws/talk") as ws2:
                    msg = ws2.receive()
                    assert msg["type"] == "websocket.close"
                    assert msg["code"] == 4409
                assert manager._current_session is not None
            mock_create.assert_called_once()


def test_talkback_session_timeout_configurable():
    """Test that session timeout is configurable for fast tests."""
    config = TalkbackConfig(session_timeout_s=0.05)
    manager = TalkbackManager(config)
    assert manager._config.session_timeout_s == 0.05


def test_talkback_simulated_mode_counts_bytes():
    """Test simulated mode (no player binary) counts bytes."""
    import asyncio
    
    config = TalkbackConfig(
        player_argv=["nonexistent_player_binary_12345"],
        fallback_argv=["also_nonexistent_12345"],
    )
    session = TalkbackSession(config)
    
    async def run_test():
        await session.start()
        assert session._simulated is True
        await session.write(b"hello")
        await session.write(b"world")
        assert session._bytes_written == 10
        await session.stop()
    
    asyncio.run(run_test())


def test_talkback_stops_soothe_audio_on_start():
    """Test that starting a talkback session stops edge_player."""
    from cradleecho.audio import edge_player
    
    original_stop = edge_player.stop
    edge_player.stop = MagicMock()
    
    try:
        config = TalkbackConfig(
            player_argv=["nonexistent_player_binary_12345"],
            fallback_argv=["also_nonexistent_12345"],
        )
        session = TalkbackSession(config)
        
        async def run_test():
            await session.start()
            edge_player.stop.assert_called_once()
            await session.stop()
        
        asyncio.run(run_test())
    finally:
        edge_player.stop = original_stop


@pytest.mark.asyncio
async def test_talkback_manager_enforces_single_talker():
    """Test TalkbackManager enforces single talker rule."""
    config = TalkbackConfig(
        player_argv=["nonexistent_player_binary_12345"],
        fallback_argv=["also_nonexistent_12345"],
        session_timeout_s=60.0,
    )
    manager = TalkbackManager(config)
    
    ws1 = AsyncMock()
    ws1.accept = AsyncMock()
    ws1.close = AsyncMock()
    ws1.receive = AsyncMock(side_effect=asyncio.CancelledError())
    
    ws2 = AsyncMock()
    ws2.accept = AsyncMock()
    ws2.close = AsyncMock()
    
    await ws1.accept()
    session1 = await manager.connect(ws1)
    assert manager._current_session is session1
    ws1.accept.assert_called_once()
    
    await ws2.accept()
    # Second connection should be rejected (close called + RuntimeError raised)
    with pytest.raises(RuntimeError, match="Another talker active"):
        await manager.connect(ws2)
    ws2.close.assert_called_with(code=4409)
    
    await manager.disconnect(session1)


@pytest.mark.asyncio
async def test_talkback_session_timeout():
    """Test session times out after configured duration."""
    config = TalkbackConfig(
        player_argv=["nonexistent_player_binary_12345"],
        fallback_argv=["also_nonexistent_12345"],
        session_timeout_s=0.05,
    )
    manager = TalkbackManager(config)
    
    ws = AsyncMock()
    ws.accept = AsyncMock()
    ws.close = AsyncMock()
    ws.receive = AsyncMock(side_effect=asyncio.CancelledError())
    
    await ws.accept()
    session = await manager.connect(ws)
    ws.accept.assert_called_once()
    
    await asyncio.sleep(0.1)
    
    # Session should be cleaned up
    assert manager._current_session is None
    # Note: manager doesn't close websocket directly; handler does that
    # The timeout watcher calls _close_current_session_locked which stops the session

@pytest.mark.parametrize("test_app", [0.3], indirect=True)
def test_talkback_cap_closes_socket_and_player(test_app):
    """The session cap stops the player AND closes the websocket (code 1000)."""
    app, manager = test_app
    fake_proc = FakePlayerProcess()
    with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_create:
        mock_create.return_value = fake_proc
        with TestClient(app) as client:
            with client.websocket_connect("/ws/talk") as ws:
                ws.send_bytes(b"\x00" * 320)
                msg = ws.receive()
                assert msg["type"] == "websocket.close"
                assert msg["code"] == 1000
    assert manager._current_session is None
    assert fake_proc._wait_called
