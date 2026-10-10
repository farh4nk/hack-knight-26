"""Listen (Pi mic -> browser) WebSocket hub with arecord fan-out."""

import asyncio
import logging
import os
import shutil
from asyncio import Queue, QueueFull
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Optional

from fastapi import WebSocket, WebSocketDisconnect

from cradleecho.config import settings

logger = logging.getLogger(__name__)

# ~40ms at 16kHz S16LE mono = 1280 bytes
CHUNK_BYTES = 1280
SUBSCRIBER_QUEUE_MAX = 50  # bounded queue per subscriber


@dataclass
class ListenConfig:
    recorder_argv: list[str] | None = None
    device: str = "default"


class ListenHub:
    """Runs a single arecord process and fans out audio chunks to subscribers."""

    def __init__(self, config: ListenConfig | None = None) -> None:
        self._config = config or ListenConfig()
        self._recorder_argv = self._config.recorder_argv
        self._device = self._config.device or "default"
        self._proc: Optional[asyncio.subprocess.Process] = None
        self._reader_task: Optional[asyncio.Task] = None
        self._subscribers: dict[int, Queue[bytes]] = {}
        self._subscriber_id = 0
        self._lock = asyncio.Lock()
        self._enabled = settings.listen_enabled

    @property
    def enabled(self) -> bool:
        return self._enabled

    async def _ensure_recorder_started(self) -> None:
        """Start the arecord process if not already running."""
        if self._proc is not None:
            return

        if self._recorder_argv is not None:
            argv = self._recorder_argv
        else:
            arecord_path = shutil.which("arecord")
            if not arecord_path:
                logger.warning("arecord not found; listen hub cannot start")
                return
            argv = [arecord_path, "-q", "-t", "raw", "-f", "S16_LE", "-r", "16000", "-c", "1", "-D", self._device, "-"]

        try:
            self._proc = await asyncio.create_subprocess_exec(
                *argv,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
            )
            self._reader_task = asyncio.create_task(self._reader_loop())
            logger.info("Listen recorder started: pid=%s", self._proc.pid)
        except Exception as e:
            logger.error("Failed to start listen recorder: %s", e)
            self._proc = None

    async def _reader_loop(self) -> None:
        """Read chunks from arecord stdout and fan out to subscribers."""
        assert self._proc is not None
        assert self._proc.stdout is not None

        try:
            while True:
                chunk = await self._proc.stdout.read(CHUNK_BYTES)
                if not chunk:
                    break
                await self._fan_out(chunk)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.warning("Listen reader loop error: %s", e)
        finally:
            logger.info("Listen reader loop ended")

    async def _fan_out(self, chunk: bytes) -> None:
        """Send chunk to all subscribers, dropping oldest if queue full."""
        if not self._subscribers:
            return

        dead: list[int] = []
        for sub_id, queue in self._subscribers.items():
            try:
                queue.put_nowait(chunk)
            except QueueFull:
                # Drop oldest and add new
                try:
                    queue.get_nowait()
                    queue.put_nowait(chunk)
                except Exception:
                    dead.append(sub_id)
            except Exception:
                dead.append(sub_id)

        for sub_id in dead:
            self._subscribers.pop(sub_id, None)

    async def subscribe(self) -> Queue[bytes]:
        """Register a new subscriber and return its queue."""
        async with self._lock:
            sub_id = self._subscriber_id
            self._subscriber_id += 1
            queue: Queue[bytes] = Queue(maxsize=SUBSCRIBER_QUEUE_MAX)
            self._subscribers[sub_id] = queue

            if len(self._subscribers) == 1:
                await self._ensure_recorder_started()

            logger.debug("Listen subscriber added: %d (total=%d)", sub_id, len(self._subscribers))
            return queue

    async def unsubscribe(self, queue: Queue[bytes]) -> None:
        """Remove a subscriber and stop recorder if last one leaves."""
        async with self._lock:
            # Find and remove by queue identity
            to_remove = [sid for sid, q in self._subscribers.items() if q is queue]
            for sid in to_remove:
                self._subscribers.pop(sid, None)

            if not self._subscribers:
                await self._stop_recorder_locked()

    async def _stop_recorder_locked(self) -> None:
        if self._reader_task is not None:
            self._reader_task.cancel()
            try:
                await self._reader_task
            except asyncio.CancelledError:
                pass
            self._reader_task = None

        if self._proc is not None:
            try:
                self._proc.terminate()
                await asyncio.wait_for(self._proc.wait(), timeout=2.0)
            except asyncio.TimeoutError:
                self._proc.kill()
                await self._proc.wait()
            except Exception:
                pass
            finally:
                self._proc = None
                logger.info("Listen recorder stopped")

    async def stop(self) -> None:
        """Stop the hub completely."""
        async with self._lock:
            await self._stop_recorder_locked()
            self._subscribers.clear()


@asynccontextmanager
async def listen_websocket(hub: ListenHub, websocket: WebSocket) -> AsyncIterator[Queue[bytes]]:
    """Context manager for a listen WebSocket connection."""
    if not hub.enabled:
        await websocket.close(code=4403)  # "Listen disabled"
        raise RuntimeError("Listen disabled")

    queue = await hub.subscribe()
    try:
        yield queue
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.warning("Listen websocket error: %s", e)
    finally:
        await hub.unsubscribe(queue)


async def handle_listen_ws(hub: ListenHub, websocket: WebSocket) -> None:
    """Handle a listen WebSocket connection."""
    await websocket.accept()

    if not hub.enabled:
        await websocket.close(code=4403)
        return

    queue = await hub.subscribe()
    try:
        while True:
            try:
                chunk = await asyncio.wait_for(queue.get(), timeout=0.1)
                await websocket.send_bytes(chunk)
            except asyncio.TimeoutError:
                # Check if client disconnected
                try:
                    msg = await asyncio.wait_for(websocket.receive(), timeout=0.01)
                    if msg["type"] == "websocket.disconnect":
                        break
                except asyncio.TimeoutError:
                    continue
                except WebSocketDisconnect:
                    break
            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.warning("Listen websocket send error: %s", e)
                break
    finally:
        await hub.unsubscribe(queue)