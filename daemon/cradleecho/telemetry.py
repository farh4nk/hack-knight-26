"""Telemetry broadcast hub and 2 Hz background processing loop."""

import asyncio
from datetime import datetime, timezone
import json
import logging
from typing import Any, Dict, Optional, Set

from fastapi import WebSocket

from cradleecho.camera import Camera
from cradleecho.classifier import SleepStateClassifier
from cradleecho.sources.base import Reading, VitalsSource

logger = logging.getLogger(__name__)


def format_telemetry_payload(
    state: str,
    reading: Reading,
    motion_index: float,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Format reading and state into the standard AGENTS.md payload."""
    dt = now or datetime.now(timezone.utc)
    ts_str = dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    return {
        "timestamp": ts_str,
        "state": state,
        "vitals": {
            "brpm": round(float(reading.brpm), 1),
            "bpm": round(float(reading.bpm), 1),
            "confidence": round(float(reading.confidence), 2),
        },
        "motion_index": round(float(motion_index), 2),
    }


class TelemetryHub:
    """Manages WebSocket subscribers and runs the 2 Hz telemetry loop."""

    def __init__(
        self,
        camera: Camera,
        source: VitalsSource,
        classifier: SleepStateClassifier,
        interval_s: float = 0.5,
    ) -> None:
        self.camera = camera
        self.source = source
        self.classifier = classifier
        self.interval_s = interval_s

        self._clients: Set[WebSocket] = set()
        self._running = False
        self._loop_task: Optional[asyncio.Task] = None
        self._latest_payload: Dict[str, Any] = format_telemetry_payload(
            state=classifier.current_state,
            reading=Reading(brpm=24.0, bpm=120.0, confidence=0.90, motion_index=0.10),
            motion_index=0.10,
        )

    def get_latest_payload(self) -> Dict[str, Any]:
        """Return the most recently generated telemetry payload."""
        return self._latest_payload

    async def connect(self, websocket: WebSocket) -> None:
        """Register a new active WebSocket connection."""
        await websocket.accept()
        self._clients.add(websocket)
        # Immediately send the latest state so client isn't waiting
        try:
            await websocket.send_text(json.dumps(self._latest_payload))
        except Exception:
            self._clients.discard(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        """Unregister a WebSocket connection."""
        self._clients.discard(websocket)

    async def broadcast(self, payload: Dict[str, Any]) -> None:
        """Broadcast JSON payload to all connected clients, dropping dead ones."""
        if not self._clients:
            return

        message = json.dumps(payload)
        dead_clients: Set[WebSocket] = set()

        for ws in list(self._clients):
            try:
                await ws.send_text(message)
            except Exception:
                dead_clients.add(ws)

        for ws in dead_clients:
            self._clients.discard(ws)

    async def step(self) -> Dict[str, Any]:
        """Execute a single telemetry cycle."""
        reading = self.source.read()

        # Motion index fallback: use camera frame-diff if source did not supply one
        if reading.motion_index is not None:
            motion = reading.motion_index
        else:
            motion = self.camera.get_motion_index()

        reading_with_motion = Reading(
            brpm=reading.brpm,
            bpm=reading.bpm,
            confidence=reading.confidence,
            motion_index=motion,
            timestamp=reading.timestamp,
        )

        state = self.classifier.update(reading_with_motion)
        payload = format_telemetry_payload(state, reading_with_motion, motion)
        self._latest_payload = payload
        await self.broadcast(payload)
        return payload

    async def _run_loop(self) -> None:
        while self._running:
            try:
                await self.step()
            except Exception as e:
                logger.error("Error in telemetry loop step: %s", e)
            await asyncio.sleep(self.interval_s)

    async def start(self) -> None:
        """Start the background 2 Hz telemetry loop."""
        if self._running:
            return
        self._running = True
        self._loop_task = asyncio.create_task(self._run_loop())

    async def stop(self) -> None:
        """Stop the background telemetry loop."""
        self._running = False
        if self._loop_task is not None:
            self._loop_task.cancel()
            try:
                await self._loop_task
            except asyncio.CancelledError:
                pass
            self._loop_task = None
