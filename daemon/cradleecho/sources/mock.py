"""Mock vitals source generating realistic random walks."""

import random
import time
from typing import Optional

from cradleecho.sources.base import Reading


class MockVitalsSource:
    """Simulates realistic infant vitals with mean-reverting random walk."""

    def __init__(self, seed: Optional[int] = None) -> None:
        self._rng = random.Random(seed)
        self._mode: Optional[str] = None
        self._brpm: float = 24.0
        self._bpm: float = 120.0
        self._confidence: float = 0.90
        self._motion_index: float = 0.10
        self._running: bool = False

    async def start(self) -> None:
        self._running = True

    async def stop(self) -> None:
        self._running = False

    def set_forced_mode(self, mode: Optional[str]) -> None:
        """Set simulation mode: 'RESTLESS' or None (normal)."""
        if mode:
            self._mode = mode.upper()
        else:
            self._mode = None

    def read(self) -> Reading:
        now = time.time()
        if self._mode == "RESTLESS":
            # Spiked vitals for restless simulation
            target_brpm = 35.0
            target_bpm = 140.0
            target_conf = 0.88
            target_motion = 0.72
        else:
            # Normal infant vitals (asleep / calm)
            target_brpm = 24.0
            target_bpm = 120.0
            target_conf = 0.90
            target_motion = 0.10

        # Mean-reverting random walk step
        self._brpm += 0.25 * (target_brpm - self._brpm) + self._rng.uniform(-0.4, 0.4)
        self._bpm += 0.25 * (target_bpm - self._bpm) + self._rng.uniform(-0.8, 0.8)
        self._confidence += 0.20 * (target_conf - self._confidence) + self._rng.uniform(-0.02, 0.02)
        self._motion_index += 0.25 * (target_motion - self._motion_index) + self._rng.uniform(-0.03, 0.03)

        # Clamping
        if self._mode == "RESTLESS":
            self._brpm = max(31.0, min(42.0, self._brpm))
            self._bpm = max(130.0, min(155.0, self._bpm))
            self._motion_index = max(0.62, min(0.85, self._motion_index))
        else:
            self._brpm = max(20.0, min(28.0, self._brpm))
            self._bpm = max(112.0, min(128.0, self._bpm))
            self._motion_index = max(0.02, min(0.25, self._motion_index))

        self._confidence = max(0.50, min(0.99, self._confidence))

        return Reading(
            brpm=self._brpm,
            bpm=self._bpm,
            confidence=self._confidence,
            motion_index=self._motion_index,
            timestamp=now,
        )
