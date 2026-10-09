"""Unit tests for the pure sleep state classifier."""

import pytest
from cradleecho.classifier import (
    STATE_ASLEEP,
    STATE_DROWSY,
    STATE_RESTLESS,
    STATE_AWAKE,
    STATE_SIGNAL_UNSTABLE,
    SleepStateClassifier,
)
from cradleecho.sources.base import Reading


class FakeClock:
    def __init__(self, start_time: float = 1000.0) -> None:
        self.time = start_time

    def now(self) -> float:
        return self.time

    def advance(self, seconds: float) -> None:
        self.time += seconds


def test_initial_state_asleep():
    clock = FakeClock()
    clf = SleepStateClassifier(clock=clock.now)
    reading = Reading(brpm=24.0, bpm=120.0, confidence=0.90, motion_index=0.10)
    state = clf.update(reading)
    assert state == STATE_ASLEEP
    assert clf.current_state == STATE_ASLEEP


def test_hysteresis_transition_to_restless():
    clock = FakeClock()
    clf = SleepStateClassifier(clock=clock.now)

    # Establish baseline asleep
    normal = Reading(brpm=24.0, bpm=120.0, confidence=0.90, motion_index=0.10)
    for _ in range(5):
        clock.advance(0.5)
        clf.update(normal)
    assert clf.current_state == STATE_ASLEEP

    # High brpm (> 24 * 1.25 = 30) -> first tick should NOT switch yet (hysteresis)
    spiked = Reading(brpm=35.0, bpm=135.0, confidence=0.88, motion_index=0.20)
    clock.advance(0.5)
    s1 = clf.update(spiked)
    assert s1 == STATE_ASLEEP, "First restless tick should not transition yet"

    # Second consecutive tick -> should transition to RESTLESS
    clock.advance(0.5)
    s2 = clf.update(spiked)
    assert s2 == STATE_RESTLESS, "Second consecutive restless tick should transition"


def test_hysteresis_transition_back_to_asleep():
    clock = FakeClock()
    clf = SleepStateClassifier(clock=clock.now)

    # Start in restless
    spiked = Reading(brpm=35.0, bpm=135.0, confidence=0.88, motion_index=0.20)
    clf.update(spiked)
    clock.advance(0.5)
    clf.update(spiked)
    assert clf.current_state == STATE_RESTLESS

    # Calm reading -> 1st tick stays RESTLESS
    calm = Reading(brpm=24.0, bpm=120.0, confidence=0.92, motion_index=0.10)
    clock.advance(0.5)
    assert clf.update(calm) == STATE_RESTLESS

    # 2nd tick transitions to ASLEEP
    clock.advance(0.5)
    assert clf.update(calm) == STATE_ASLEEP


def test_signal_unstable_switches_immediately():
    clock = FakeClock()
    clf = SleepStateClassifier(clock=clock.now)

    # Established asleep
    calm = Reading(brpm=24.0, bpm=120.0, confidence=0.90, motion_index=0.10)
    clf.update(calm)
    assert clf.current_state == STATE_ASLEEP

    # Low confidence (< 0.40) -> switches immediately on first tick
    low_conf = Reading(brpm=24.0, bpm=120.0, confidence=0.25, motion_index=0.10)
    clock.advance(0.5)
    state = clf.update(low_conf)
    assert state == STATE_SIGNAL_UNSTABLE
    assert clf.current_state == STATE_SIGNAL_UNSTABLE


def test_recovery_from_signal_unstable_requires_hysteresis():
    clock = FakeClock()
    clf = SleepStateClassifier(clock=clock.now)

    # Start with unstable signal
    unstable = Reading(brpm=0.0, bpm=0.0, confidence=0.10, motion_index=0.0)
    clf.update(unstable)
    assert clf.current_state == STATE_SIGNAL_UNSTABLE

    # Good signal tick 1 -> remains unstable
    good = Reading(brpm=24.0, bpm=120.0, confidence=0.90, motion_index=0.10)
    clock.advance(0.5)
    assert clf.update(good) == STATE_SIGNAL_UNSTABLE

    # Good signal tick 2 -> switches to ASLEEP
    clock.advance(0.5)
    assert clf.update(good) == STATE_ASLEEP


def test_motion_triggers_awake_and_restless():
    clock = FakeClock()
    clf = SleepStateClassifier(clock=clock.now)

    calm = Reading(brpm=24.0, bpm=120.0, confidence=0.90, motion_index=0.10)
    clf.update(calm)

    # Motion > 0.85 -> AWAKE (after 2 ticks)
    awake_reading = Reading(brpm=25.0, bpm=120.0, confidence=0.90, motion_index=0.90)
    clock.advance(0.5)
    assert clf.update(awake_reading) == STATE_ASLEEP
    clock.advance(0.5)
    assert clf.update(awake_reading) == STATE_AWAKE

    # Motion > 0.60 (but <= 0.85) -> RESTLESS (after 2 ticks)
    restless_motion = Reading(brpm=25.0, bpm=120.0, confidence=0.90, motion_index=0.70)
    clock.advance(0.5)
    clf.update(restless_motion)
    clock.advance(0.5)
    assert clf.update(restless_motion) == STATE_RESTLESS


def test_drowsy_state():
    clock = FakeClock()
    clf = SleepStateClassifier(clock=clock.now)

    # Baseline 24
    calm = Reading(brpm=24.0, bpm=120.0, confidence=0.90, motion_index=0.10)
    clf.update(calm)

    # Brpm 18 (< 20) with low motion is neither asleep, restless, awake nor unstable -> DROWSY
    drowsy_reading = Reading(brpm=18.0, bpm=115.0, confidence=0.88, motion_index=0.15)
    clock.advance(0.5)
    clf.update(drowsy_reading)
    clock.advance(0.5)
    assert clf.update(drowsy_reading) == STATE_DROWSY


def test_force_restless_and_expiry():
    clock = FakeClock()
    clf = SleepStateClassifier(clock=clock.now)

    calm = Reading(brpm=24.0, bpm=120.0, confidence=0.90, motion_index=0.10)
    clf.update(calm)
    assert clf.current_state == STATE_ASLEEP

    # Force RESTLESS for 15s
    expiry = clf.force_restless(duration_s=15.0)
    assert expiry == 1015.0
    assert clf.current_state == STATE_RESTLESS

    # Even with calm readings, forced RESTLESS holds
    clock.advance(5.0)
    assert clf.update(calm) == STATE_RESTLESS
    clock.advance(5.0)
    assert clf.update(calm) == STATE_RESTLESS

    # At 15s, expiry is reached
    clock.advance(5.1)  # now 1015.1
    # Once expired, update evaluates normally with 2-tick hysteresis
    assert clf.update(calm) == STATE_RESTLESS
    clock.advance(0.5)
    assert clf.update(calm) == STATE_ASLEEP
