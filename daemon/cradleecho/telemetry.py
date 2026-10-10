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
    camera: Optional[Any] = None,
    source: Optional[Any] = None,
) -> Dict[str, Any]:
    """Format reading and state into the standard AGENTS.md payload."""
    dt = now or datetime.now(timezone.utc)
    ts_str = dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    # Build camera telemetry object
    is_live = getattr(camera, "is_live", lambda: False)() if camera else False

    gate_obj = getattr(source, "gate", None)
    if gate_obj is None:
        gate_state = "DISABLED"
        framing = "UNKNOWN"
    else:
        gate_state = "OPEN" if getattr(gate_obj, "is_active", False) else "CLOSED"
        reason = getattr(gate_obj, "reason", "no_face")
        mapping = {
            "ok": "OK",
            "no_face": "NO_FACE",
            "multiple_faces": "MULTIPLE_FACES",
            "too_small": "TOO_SMALL",
            "off_center": "OFF_CENTER",
            "no_chest_room": "NO_CHEST_ROOM"
        }
        framing = mapping.get(reason, "UNKNOWN")

    session_running = getattr(source, "session_running", False) if source else False
    sdk_code = getattr(source, "validation_code", None) if session_running else None
    sdk_hint = getattr(source, "raw_validation_hint", None) if session_running else None

    camera_info = {
        "live": is_live,
        "gate": gate_state,
        "framing": framing,
        "sdk_code": sdk_code,
        "sdk_hint": sdk_hint,
    }

    return {
        "timestamp": ts_str,
        "state": state,
        "vitals": {
            "brpm": round(float(reading.brpm), 1),
            "bpm": round(float(reading.bpm), 1),
            "confidence": round(float(reading.confidence), 2),
        },
        "motion_index": round(float(motion_index), 2),
        "camera": camera_info,
    }


import time
from cradleecho.config import settings

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
        self._forced_unstable_until: float = 0.0
        self._latest_payload: Dict[str, Any] = format_telemetry_payload(
            state="SIGNAL_UNSTABLE",
            reading=Reading(brpm=0.0, bpm=0.0, confidence=0.0, motion_index=0.0),
            motion_index=0.0,
            camera=self.camera,
            source=self.source,
        )

    def force_unstable(self, seconds: float) -> float:
        self._forced_unstable_until = time.time() + seconds
        return self._forced_unstable_until

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
        
        async def _send(ws):
            try:
                await asyncio.wait_for(ws.send_text(message), timeout=1.0)
                return ws, True
            except Exception:
                return ws, False

        results = await asyncio.gather(*[_send(ws) for ws in self._clients], return_exceptions=True)
        
        dead_clients: Set[WebSocket] = set()
        for res in results:
            if isinstance(res, tuple):
                ws, success = res
                if not success:
                    dead_clients.add(ws)
            else:
                pass # exception raised

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

        forced = time.time() < self._forced_unstable_until
        cam_live = getattr(self.camera, "is_live", lambda: False)()
        cam_brightness = getattr(self.camera, "get_brightness", lambda: None)()
        gate = cam_live and cam_brightness is not None and cam_brightness < settings.min_brightness
        
        reading_confidence = 0.0 if forced or gate else reading.confidence

        reading_with_motion = Reading(
            brpm=reading.brpm,
            bpm=reading.bpm,
            confidence=reading_confidence,
            motion_index=motion,
            timestamp=reading.timestamp,
        )

        state = self.classifier.update(reading_with_motion)
        payload = format_telemetry_payload(state, reading_with_motion, motion, camera=self.camera, source=self.source)
        self._latest_payload = payload
        await self.broadcast(payload)
        return payload

    async def _run_loop(self) -> None:
        loop = asyncio.get_running_loop()
        next_deadline = loop.time() + self.interval_s
        while self._running:
            try:
                await self.step()
            except Exception as e:
                logger.error("Error in telemetry loop step: %s", e)
            
            now = loop.time()
            if now > next_deadline + self.interval_s:
                # >1 interval behind, skip ahead (no bursting)
                next_deadline = now + self.interval_s
            else:
                while next_deadline <= now:
                    next_deadline += self.interval_s
            
            delay = max(0.0, next_deadline - loop.time())
            await asyncio.sleep(delay)

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
