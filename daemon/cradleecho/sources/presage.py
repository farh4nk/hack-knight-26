"""Presage (SmartSpectra) subprocess adapter reading NDJSON from stdout."""

import asyncio
import json
import logging
import os
import shlex
import re
import time

import cv2
import numpy as np

from cradleecho.config import settings
from cradleecho.sources.base import Reading

logger = logging.getLogger(__name__)


class PresageVitalsSource:
    """Subprocess adapter spawning Presage C++ bridge (or fake_bridge)."""

    _frame_size: tuple[int, int] | None = None
    _validation: tuple[str, str] | None = None

    @property
    def session_running(self) -> bool:
        return self._proc is not None

    @property
    def gate(self):
        return self._gate

    @property
    def validation_code(self) -> str | None:
        if self._validation:
            return self._validation[0]
        return None

    @property
    def raw_validation_hint(self) -> str | None:
        if self._validation:
            return self._validation[1] if self._validation[1] else None
        return None

    @property
    def validation_hint(self) -> str:
        if self._validation:
            code, hint = self._validation
            return f"{code}: {hint}" if hint else code
        return ""

    def __init__(
        self,
        cmd: str | list[str] | None = None,
        stale_timeout_s: float = 3.0,
        max_fps: float | None = None,
    ) -> None:
        if cmd is None:
            raw_cmd = settings.presage_cmd
            self._cmd_args = shlex.split(raw_cmd)
        elif isinstance(cmd, str):
            self._cmd_args = shlex.split(cmd)
        else:
            self._cmd_args = list(cmd)

        self._stale_timeout_s = stale_timeout_s

        # `--stdin WxH` means the bridge reads raw BGR frames from our pipe.
        self._frame_size: tuple[int, int] | None = None
        for i, arg in enumerate(self._cmd_args[:-1]):
            m = re.fullmatch(r"(\d+)x(\d+)", self._cmd_args[i + 1]) if arg == "--stdin" else None
            if m:
                self._frame_size = (int(m.group(1)), int(m.group(2)))
        self._min_frame_interval = 1.0 / (max_fps or settings.presage_fps)
        self._last_push = 0.0
        self._write_pending = False
        self._loop: asyncio.AbstractEventLoop | None = None
        self._latest_reading: Reading | None = None
        self._last_received_time: float | None = None
        self._running = False
        self._proc: asyncio.subprocess.Process | None = None
        self._worker_task: asyncio.Task | None = None
        self._mode: str | None = None
        self._gate = None
        self._gate_active = True
        self._gate_event: asyncio.Event | None = None

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._loop = asyncio.get_running_loop()
        self._gate_event = asyncio.Event()
        if self._gate_active:
            self._gate_event.set()
        self._worker_task = asyncio.create_task(self._worker_loop())

    async def stop(self) -> None:
        self._running = False
        if self._gate_event:
            self._gate_event.set()
        if self._proc is not None:
            try:
                self._proc.terminate()
                await asyncio.wait_for(self._proc.wait(), timeout=1.5)
            except (TimeoutError, ProcessLookupError):
                try:
                    self._proc.kill()
                    await self._proc.wait()
                except ProcessLookupError:
                    pass
            self._proc = None
        self._validation = None

        if self._worker_task is not None:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
            self._worker_task = None

    def set_gate(self, gate) -> None:
        self._gate = gate
        self._gate_active = False
        if self._gate_event:
            self._gate_event.clear()

    @property
    def gate_enabled(self) -> bool:
        return self._gate is not None

    def _handle_gate_inactive(self) -> None:
        if self._gate_event:
            self._gate_event.clear()
        self._latest_reading = None
        self._last_received_time = None
        self._validation = None
        if self._proc is not None:
            logger.info("face gate: stopping Presage session")
            try:
                self._proc.terminate()
            except ProcessLookupError:
                pass

    @property
    def wants_frames(self) -> bool:
        return self._frame_size is not None

    def push_frame(self, frame: np.ndarray) -> None:
        """Hand a BGR frame to the bridge. Called from the camera thread; never blocks.

        Frames are dropped when throttled or when the previous write has not
        been flushed to the pipe yet.
        """
        if self._frame_size is None or self._loop is None or not self._running:
            return

        if self._gate is not None:
            was_active = self._gate_active
            is_active = self._gate.update(frame)
            self._gate_active = is_active
            if is_active and not was_active:
                if self._gate_event:
                    self._loop.call_soon_threadsafe(self._gate_event.set)
            elif not is_active and was_active:
                self._loop.call_soon_threadsafe(self._handle_gate_inactive)

        if not self._gate_active:
            return

        now = time.monotonic()
        if self._write_pending or now - self._last_push < self._min_frame_interval:
            return
        self._last_push = now
        w, h = self._frame_size
        if frame.shape[1] != w or frame.shape[0] != h:
            frame = cv2.resize(frame, (w, h), interpolation=cv2.INTER_AREA)
        self._write_pending = True
        try:
            self._loop.call_soon_threadsafe(self._write_frame, np.ascontiguousarray(frame).tobytes())
        except RuntimeError:  # loop closed during shutdown
            self._write_pending = False

    def _write_frame(self, data: bytes) -> None:
        try:
            proc = self._proc
            if proc is None or proc.stdin is None or proc.stdin.is_closing():
                return
            # Bridge is not keeping up: drop rather than queue stale frames.
            if proc.stdin.transport.get_write_buffer_size() > len(data):
                return
            proc.stdin.write(data)
        except (BrokenPipeError, ConnectionResetError, RuntimeError):
            pass
        finally:
            self._write_pending = False

    def set_forced_mode(self, mode: str | None) -> None:
        self._mode = mode

    def read(self) -> Reading:
        now = time.time()
        # Stale-aware check: no message within timeout => confidence = 0.0 (SIGNAL_UNSTABLE)
        if self._last_received_time is None or (now - self._last_received_time) > self._stale_timeout_s:
            return Reading(
                brpm=0.0,
                bpm=0.0,
                confidence=0.0,
                motion_index=None,
                timestamp=now,
            )

        if self._latest_reading is not None:
            return self._latest_reading

        return Reading(
            brpm=0.0,
            bpm=0.0,
            confidence=0.0,
            motion_index=None,
            timestamp=now,
        )

    async def _worker_loop(self) -> None:
        backoff = 1.0
        while self._running:
            if not self._gate_active:
                if self._gate_event:
                    await self._gate_event.wait()
                if not self._running:
                    break
                logger.info("face gate: starting Presage session")

            try:
                env = os.environ.copy()
                if settings.presage_api_key:
                    env["PRESAGE_API_KEY"] = settings.presage_api_key.get_secret_value()

                logger.info("Spawning Presage bridge: %s", " ".join(self._cmd_args))
                self._validation = None
                self._proc = await asyncio.create_subprocess_exec(
                    *self._cmd_args,
                    stdin=asyncio.subprocess.PIPE if self._frame_size else asyncio.subprocess.DEVNULL,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=None,  # Logs pass directly to parent stderr
                    env=env,
                )

                while self._running and self._proc.stdout is not None:
                    line = await self._proc.stdout.readline()
                    if not line:
                        break  # EOF

                    try:
                        data = json.loads(line.decode("utf-8").strip())
                        if "validation" in data:
                            self._validation = (data.get("validation", ""), data.get("hint", ""))
                            continue

                        brpm = float(data.get("brpm", 0.0))
                        bpm = float(data.get("bpm", 0.0))
                        conf = float(data.get("confidence", 0.0))
                        motion_val = data.get("motion_index")
                        motion = float(motion_val) if motion_val is not None else None
                        timestamp = float(data.get("t", time.time()))

                        if brpm == 0.0 and bpm == 0.0:
                            conf = 0.0

                        self._latest_reading = Reading(
                            brpm=brpm,
                            bpm=bpm,
                            confidence=conf,
                            motion_index=motion,
                            timestamp=timestamp,
                        )
                        self._last_received_time = time.time()
                        backoff = 1.0
                    except (json.JSONDecodeError, ValueError, TypeError) as parse_err:
                        logger.warning("Error parsing Presage NDJSON: %s", parse_err)

                if self._proc is not None:
                    try:
                        await asyncio.wait_for(self._proc.wait(), timeout=1.5)
                    except (TimeoutError, ProcessLookupError):
                        try:
                            self._proc.kill()
                            await self._proc.wait()
                        except ProcessLookupError:
                            pass

            except Exception as e:
                logger.error("Presage subprocess error: %s", e)

            self._proc = None
            self._validation = None

            if self._running:
                if not self._gate_active:
                    continue

                logger.warning("Presage bridge exited. Reconnecting in %.1fs...", backoff)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2.0, 5.0)
