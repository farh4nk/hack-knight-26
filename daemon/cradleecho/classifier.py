"""Sleep state rolling classifier with injectable clock and hysteresis."""

import collections
import statistics
import time
from typing import Callable, Deque, List, Optional, Tuple

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


class SleepStateClassifier:
    """Rolling state machine classifier for infant sleep quality."""

    def __init__(
        self,
        clock: Optional[Callable[[], float]] = None,
        window_duration_s: float = 10.0,
        hysteresis_ticks: int = 2,
    ) -> None:
        self._clock = clock if clock is not None else time.time
        self._window_duration_s = window_duration_s
        self._hysteresis_ticks = hysteresis_ticks

        self._readings: Deque[Tuple[float, Reading]] = collections.deque()
        self._current_state: Optional[str] = None
        self._pending_state: Optional[str] = None
        self._pending_count: int = 0
        self._forced_until: Optional[float] = None

    @property
    def current_state(self) -> str:
        """Return the current active state (defaulting to ASLEEP if uninitialized)."""
        if self._is_forced_restless():
            return STATE_RESTLESS
        return self._current_state if self._current_state is not None else STATE_ASLEEP

    def force_restless(self, duration_s: float = 15.0) -> float:
        """Force the state to RESTLESS for duration_s seconds. Returns expiry epoch."""
        expiry = self._clock() + duration_s
        self._forced_until = expiry
        self._current_state = STATE_RESTLESS
        self._pending_state = None
        self._pending_count = 0
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

    def _compute_baseline_brpm(self) -> float:
        valid_brpms: List[float] = [
            r.brpm
            for _, r in self._readings
            if r.confidence >= 0.40 and 20.0 <= r.brpm <= 30.0
        ]
        if not valid_brpms:
            any_valid = [r.brpm for _, r in self._readings if r.confidence >= 0.40]
            if any_valid:
                med = float(statistics.median(any_valid))
                return min(med, 26.0)
            return 24.0
        return float(statistics.median(valid_brpms))

    def evaluate_candidate(self, reading: Reading, baseline_brpm: float) -> str:
        """Compute the instantaneous candidate state for a single reading."""
        if reading.confidence < 0.40:
            return STATE_SIGNAL_UNSTABLE

        motion = reading.motion_index if reading.motion_index is not None else 0.0

        if motion > 0.85:
            return STATE_AWAKE
        elif (baseline_brpm > 0 and reading.brpm > baseline_brpm * 1.25) or motion > 0.60:
            return STATE_RESTLESS
        elif 20.0 <= reading.brpm <= 30.0 and motion < 0.30:
            return STATE_ASLEEP
        else:
            return STATE_DROWSY

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
            return STATE_RESTLESS

        baseline_brpm = self._compute_baseline_brpm()
        candidate = self.evaluate_candidate(reading, baseline_brpm)

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
