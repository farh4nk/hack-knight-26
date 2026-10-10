"""Sleep state rolling classifier with injectable clock and hysteresis.

Rules, in priority order (thresholds live in ClassifierConfig / CRADLEECHO_* env vars):

  SIGNAL_UNSTABLE  confidence too low, or no breathing estimate yet (Presage warm-up)
  AWAKE            clear movement (motion >= awake_motion), or breathing outside the
                   sleeping range (too slow/fast to be asleep)
  RESTLESS         a sleeper stirring: moderate movement (motion >= restless_motion) with
                   breathing still in the sleeping range, or breathing >25% above the baby's
                   own sleeping baseline
  ASLEEP           breathing in the sleeping range AND calm (motion < calm_motion), held steadily
                   for asleep_hold_s; before that the state is DROWSY
  DROWSY           settling: breathing in range, little movement, but not calm for long enough
                   (or movement between calm and restless)

Awake is the default for anything that doesn't look like settled sleep, so a person sitting at a
desk reads as AWAKE rather than "drifting off".
"""

import collections
import statistics
import time
from dataclasses import dataclass
from typing import Callable, Deque, List, Optional, Tuple

from cradleecho.config import settings
from cradleecho.sources.base import Reading

STATE_ASLEEP = "ASLEEP"
STATE_DROWSY = "DROWSY"
STATE_RESTLESS = "RESTLESS"
STATE_AWAKE = "AWAKE"
STATE_SIGNAL_UNSTABLE = "SIGNAL_UNSTABLE"

VALID_STATES = {
    STATE_ASLEEP,
    STATE_DROWSY,
    STATE_RESTLESS,
    STATE_AWAKE,
    STATE_SIGNAL_UNSTABLE,
}


@dataclass(frozen=True)
class ClassifierConfig:
    asleep_brpm_min: float = 22.0
    asleep_brpm_max: float = 40.0
    calm_motion: float = 0.10
    restless_motion: float = 0.20
    awake_motion: float = 0.45
    asleep_hold_s: float = 20.0
    min_valid_brpm: float = 6.0
    spike_ratio: float = 1.25
    min_confidence: float = 0.40

    @classmethod
    def from_settings(cls) -> "ClassifierConfig":
        return cls(
            asleep_brpm_min=settings.asleep_brpm_min,
            asleep_brpm_max=settings.asleep_brpm_max,
            calm_motion=settings.calm_motion,
            restless_motion=settings.restless_motion,
            awake_motion=settings.awake_motion,
            asleep_hold_s=settings.asleep_hold_s,
            min_valid_brpm=settings.min_valid_brpm,
        )

    def in_sleep_band(self, brpm: float) -> bool:
        return self.asleep_brpm_min <= brpm <= self.asleep_brpm_max


class SleepStateClassifier:
    """Rolling state machine classifier for infant sleep quality."""

    def __init__(
        self,
        clock: Optional[Callable[[], float]] = None,
        window_duration_s: float = 10.0,
        hysteresis_ticks: int = 2,
        config: Optional[ClassifierConfig] = None,
    ) -> None:
        self._clock = clock if clock is not None else time.time
        self._window_duration_s = window_duration_s
        self._hysteresis_ticks = hysteresis_ticks
        self.config = config if config is not None else ClassifierConfig.from_settings()

        self._readings: Deque[Tuple[float, Reading]] = collections.deque()
        self._current_state: Optional[str] = None
        self._pending_state: Optional[str] = None
        self._pending_count: int = 0
        self._forced_until: Optional[float] = None
        # When the current run of "settling" (ASLEEP/DROWSY candidates) began.
        self._settle_since: Optional[float] = None

    @property
    def current_state(self) -> str:
        """Current state; SIGNAL_UNSTABLE until the first reading arrives."""
        if self._is_forced_restless():
            return STATE_RESTLESS
        return self._current_state if self._current_state is not None else STATE_SIGNAL_UNSTABLE

    def force_restless(self, duration_s: float = 15.0) -> float:
        """Force the state to RESTLESS for duration_s seconds. Returns expiry epoch."""
        expiry = self._clock() + duration_s
        self._forced_until = expiry
        self._current_state = STATE_RESTLESS
        self._pending_state = None
        self._pending_count = 0
        self._settle_since = None
        return expiry

    def _is_forced_restless(self) -> bool:
        if self._forced_until is None:
            return False
        if self._clock() < self._forced_until:
            return True
        self._forced_until = None
        return False

    def _prune_window(self, now: float) -> None:
        cutoff = now - self._window_duration_s
        while self._readings and self._readings[0][0] < cutoff:
            self._readings.popleft()

    def _compute_baseline_brpm(self) -> Optional[float]:
        """Median breathing rate over recent in-range readings, or None without a sleep baseline."""
        c = self.config
        in_band: List[float] = [
            r.brpm
            for _, r in self._readings
            if r.confidence >= c.min_confidence and c.in_sleep_band(r.brpm)
        ]
        return float(statistics.median(in_band)) if in_band else None

    def evaluate_candidate(self, reading: Reading, baseline_brpm: Optional[float]) -> str:
        """Instantaneous candidate state for one reading (before the asleep-hold is applied)."""
        c = self.config
        if reading.confidence < c.min_confidence or reading.brpm < c.min_valid_brpm:
            return STATE_SIGNAL_UNSTABLE

        motion = reading.motion_index if reading.motion_index is not None else 0.0

        if motion >= c.awake_motion:
            return STATE_AWAKE
        if motion >= c.restless_motion:
            # Restless = a sleeper stirring. Moving while breathing outside the sleeping range
            # is just someone who is awake (and must not trigger auto-soothe).
            return STATE_RESTLESS if c.in_sleep_band(reading.brpm) else STATE_AWAKE
        # A breathing spike only counts against a real sleeping baseline.
        if baseline_brpm is not None and reading.brpm > baseline_brpm * c.spike_ratio:
            return STATE_RESTLESS
        if not c.in_sleep_band(reading.brpm):
            return STATE_AWAKE
        return STATE_ASLEEP if motion < c.calm_motion else STATE_DROWSY

    def update(self, reading: Reading) -> str:
        """Incorporate a new reading and return the resulting state."""
        now = self._clock()

        # Update rolling history
        self._readings.append((now, reading))
        self._prune_window(now)

        # If forced RESTLESS is active, stay RESTLESS
        if self._is_forced_restless():
            self._current_state = STATE_RESTLESS
            self._pending_state = None
            self._pending_count = 0
            self._settle_since = None
            return STATE_RESTLESS

        candidate = self.evaluate_candidate(reading, self._compute_baseline_brpm())

        # Asleep must be earned: calm in-range breathing has to hold for asleep_hold_s.
        if candidate in (STATE_ASLEEP, STATE_DROWSY):
            if self._settle_since is None:
                self._settle_since = now
            if candidate == STATE_ASLEEP and now - self._settle_since < self.config.asleep_hold_s:
                candidate = STATE_DROWSY
        else:
            self._settle_since = None

        # Initial state adoption
        if self._current_state is None:
            self._current_state = candidate
            self._pending_state = None
            self._pending_count = 0
            return self._current_state

        # Same state: reset pending counter
        if candidate == self._current_state:
            self._pending_state = None
            self._pending_count = 0
            return self._current_state

        # SIGNAL_UNSTABLE transitions immediately
        if candidate == STATE_SIGNAL_UNSTABLE:
            self._current_state = STATE_SIGNAL_UNSTABLE
            self._pending_state = None
            self._pending_count = 0
            return self._current_state

        # All other transitions require hysteresis (holding for hysteresis_ticks)
        if candidate == self._pending_state:
            self._pending_count += 1
            if self._pending_count >= self._hysteresis_ticks:
                self._current_state = candidate
                self._pending_state = None
                self._pending_count = 0
        else:
            self._pending_state = candidate
            self._pending_count = 1

        return self._current_state
