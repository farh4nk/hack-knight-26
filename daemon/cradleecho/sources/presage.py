"""Presage (SmartSpectra) subprocess adapter reading NDJSON from stdout."""

import asyncio
import json
import logging
import os
import shlex
import sys
import time
from typing import List, Optional, Union

from cradleecho.sources.base import Reading

logger = logging.getLogger(__name__)


class PresageVitalsSource:
    """Subprocess adapter spawning Presage C++ bridge (or fake_bridge)."""

    def __init__(
        self,
        cmd: Optional[Union[str, List[str]]] = None,
        stale_timeout_s: float = 3.0,
    ) -> None:
        if cmd is None:
            raw_cmd = os.getenv(
                "CRADLEECHO_PRESAGE_CMD",
                f"{sys.executable} presage_bridge/fake_bridge.py",
            )
            self._cmd_args = shlex.split(raw_cmd)
        elif isinstance(cmd, str):
            self._cmd_args = shlex.split(cmd)
        else:
            self._cmd_args = list(cmd)

        self._stale_timeout_s = stale_timeout_s
        self._latest_reading: Optional[Reading] = None
        self._last_received_time: Optional[float] = None
        self._running = False
        self._proc: Optional[asyncio.subprocess.Process] = None
        self._worker_task: Optional[asyncio.Task] = None
        self._mode: Optional[str] = None

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._worker_task = asyncio.create_task(self._worker_loop())

    async def stop(self) -> None:
        self._running = False
        if self._proc is not None:
            try:
                self._proc.terminate()
                await asyncio.wait_for(self._proc.wait(), timeout=1.5)
            except (asyncio.TimeoutError, ProcessLookupError):
                try:
                    self._proc.kill()
                    await self._proc.wait()
                except ProcessLookupError:
                    pass
            self._proc = None

        if self._worker_task is not None:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
            self._worker_task = None

    def set_forced_mode(self, mode: Optional[str]) -> None:
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
            try:
                logger.info("Spawning Presage bridge: %s", " ".join(self._cmd_args))
                self._proc = await asyncio.create_subprocess_exec(
                    *self._cmd_args,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=None,  # Logs pass directly to parent stderr
                )

                while self._running and self._proc.stdout is not None:
                    line = await self._proc.stdout.readline()
                    if not line:
                        break  # EOF

                    try:
                        data = json.loads(line.decode("utf-8").strip())
                        brpm = float(data.get("brpm", 0.0))
                        bpm = float(data.get("bpm", 0.0))
                        conf = float(data.get("confidence", 0.0))
                        motion_val = data.get("motion_index")
                        motion = float(motion_val) if motion_val is not None else None
                        timestamp = float(data.get("t", time.time()))

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
                    await self._proc.wait()

            except Exception as e:
                logger.error("Presage subprocess error: %s", e)

            if self._running:
                logger.warning("Presage bridge exited. Reconnecting in %.1fs...", backoff)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2.0, 5.0)
