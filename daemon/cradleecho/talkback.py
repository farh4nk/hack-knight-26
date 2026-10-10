"""Talkback (parent -> Pi speaker) WebSocket session and manager."""

import asyncio
import logging
import shutil
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Optional

from fastapi import WebSocket, WebSocketDisconnect

from cradleecho.audio import edge_player
from cradleecho.config import settings

logger = logging.getLogger(__name__)

DEFAULT_PLAYER_ARGS = [
    "aplay",
    "-q",
    "-t",
    "raw",
    "-f",
    "S16_LE",
    "-r",
    "16000",
    "-c",
    "1",
    "-",
]
FALLBACK_PLAYER_ARGS = [
    "ffplay",
    "-nodisp",
    "-loglevel",
    "quiet",
    "-f",
    "s16le",
    "-ar",
    "16000",
    "-ac",
    "1",
    "-i",
    "-",
]
SESSION_TIMEOUT_S = 120.0
CHUNK_MAX_BYTES = 3200  # ~100ms at 16kHz S16LE mono


@dataclass
class TalkbackConfig:
    player_argv: list[str] | None = None
    fallback_argv: list[str] | None = None
    session_timeout_s: float = SESSION_TIMEOUT_S


class TalkbackSession:
    """Manages a single parent-to-speaker audio session."""

    def __init__(self, config: TalkbackConfig | None = None) -> None:
        self._config = config or TalkbackConfig()
        self._player_argv = self._config.player_argv or DEFAULT_PLAYER_ARGS
        self._fallback_argv = self._config.fallback_argv or FALLBACK_PLAYER_ARGS
        self._session_timeout = self._config.session_timeout_s
        self._proc: Optional[asyncio.subprocess.Process] = None
        self._bytes_written = 0
        self._simulated = False
        self._started = False

    async def start(self) -> None:
        """Start the audio player subprocess."""
        if self._started:
            return
        self._started = True

        # Stop any soothe audio that might be playing
        edge_player.stop()

        player_bin = self._player_argv[0] if self._player_argv else "aplay"
        fallback_bin = self._fallback_argv[0] if self._fallback_argv else "ffplay"

        if not shutil.which(player_bin) and not shutil.which(fallback_bin):
            logger.info("No audio player binary found (aplay/ffplay missing). Talkback simulated.")
            self._simulated = True
            return

        argv = self._player_argv if shutil.which(player_bin) else self._fallback_argv
        try:
            self._proc = await asyncio.create_subprocess_exec(
                *argv,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            logger.info("Talkback player started: pid=%s", self._proc.pid)
        except Exception as e:
            logger.warning("Failed to start talkback player %s: %s; falling back to simulated mode", argv, e)
            self._simulated = True
            self._proc = None

    async def write(self, data: bytes) -> None:
        """Write PCM frames to the player stdin."""
        if self._simulated:
            self._bytes_written += len(data)
            if self._bytes_written == len(data):
                logger.info("Talkback simulated: received first chunk (%d bytes)", len(data))
            return

        if self._proc is None or self._proc.stdin is None:
            return

        try:
            self._proc.stdin.write(data)
            await self._proc.stdin.drain()
        except (BrokenPipeError, ConnectionResetError, OSError):
            logger.debug("Talkback player stdin closed")
        except Exception as e:
            logger.warning("Error writing to talkback player: %s", e)

    async def stop(self) -> None:
        """Stop the player subprocess cleanly."""
        if self._simulated:
            logger.info("Talkback simulated session ended: %d bytes total", self._bytes_written)
            self._simulated = False
            self._bytes_written = 0
            self._started = False
            return

        if self._proc is not None:
            try:
                if self._proc.stdin is not None:
                    self._proc.stdin.close()
                await asyncio.wait_for(self._proc.wait(), timeout=2.0)
            except asyncio.TimeoutError:
                self._proc.kill()
                await self._proc.wait()
            except Exception:
                pass
            finally:
                self._proc = None

        self._started = False
        logger.info("Talkback player stopped")


class TalkbackManager:
    """Enforces single-talker rule and session timeout."""

    def __init__(self, config: TalkbackConfig | None = None) -> None:
        self._config = config or TalkbackConfig()
        self._current_session: Optional[TalkbackSession] = None
        self._timeout_task: Optional[asyncio.Task] = None
        self._ws: Optional[WebSocket] = None
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket) -> TalkbackSession:
        """Accept a new talkback connection, rejecting if one is active."""
        async with self._lock:
            if self._current_session is not None:
                await websocket.close(code=4409)  # "Another talker active"
                raise RuntimeError("Another talker active")

            session = TalkbackSession(self._config)
            await session.start()
            self._current_session = session
            self._ws = websocket

            self._timeout_task = asyncio.create_task(self._timeout_watcher(session))
            logger.info("Talkback session started")
            return session

    async def _timeout_watcher(self, session: TalkbackSession) -> None:
        try:
            await asyncio.sleep(self._config.session_timeout_s)
        except asyncio.CancelledError:
            return
        ws: Optional[WebSocket] = None
        async with self._lock:
            if self._current_session is session:
                logger.info("Talkback session timed out after %.0fs", self._config.session_timeout_s)
                ws = self._ws
                # Detach this task first: _close_current_session_locked would otherwise await itself.
                self._timeout_task = None
                await self._close_current_session_locked(code=1000)
        # Close the socket outside the lock: the handler's cleanup takes the same lock.
        if ws is not None:
            try:
                await ws.close(code=1000)
            except Exception:
                pass

    async def disconnect(self, session: TalkbackSession) -> None:
        """Disconnect a session (called when WebSocket closes)."""
        async with self._lock:
            if self._current_session is session:
                await self._close_current_session_locked(code=1000)

    async def _close_current_session_locked(self, code: int = 1000) -> None:
        if self._current_session is not None:
            await self._current_session.stop()
            self._current_session = None
            self._ws = None
        if self._timeout_task is not None:
            self._timeout_task.cancel()
            try:
                await self._timeout_task
            except asyncio.CancelledError:
                pass
            self._timeout_task = None


@asynccontextmanager
async def talkback_websocket(
    manager: TalkbackManager, websocket: WebSocket
) -> AsyncIterator[TalkbackSession]:
    """Context manager for a talkback WebSocket connection."""
    session = await manager.connect(websocket)
    try:
        yield session
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.warning("Talkback session error: %s", e)
    finally:
        await manager.disconnect(session)


async def handle_talkback_ws(manager: TalkbackManager, websocket: WebSocket) -> None:
    """Handle a talkback WebSocket connection."""
    await websocket.accept()
    try:
        cm = talkback_websocket(manager, websocket)
        session = await cm.__aenter__()
    except RuntimeError:
        return  # another talker is active; the socket was already closed with 4409
    try:
        while True:
            msg = await websocket.receive()
            if msg["type"] == "websocket.disconnect":
                break
            data = msg.get("bytes")
            if not data:
                continue  # ignore non-binary messages
            for i in range(0, len(data), CHUNK_MAX_BYTES):
                await session.write(data[i : i + CHUNK_MAX_BYTES])
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.warning("Talkback websocket error: %s", e)
    finally:
        await cm.__aexit__(None, None, None)
