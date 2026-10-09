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

def test_boundary_confidence():
    clock = FakeClock()
    clf = SleepStateClassifier(clock=clock.now)

    # Establish baseline asleep
    clf.update(Reading(brpm=24.0, bpm=120.0, confidence=0.90, motion_index=0.10))
    
    # 0.40 is stable
    clock.advance(0.5)
    assert clf.update(Reading(brpm=24.0, bpm=120.0, confidence=0.40, motion_index=0.10)) == STATE_ASLEEP
    
    # 0.39 is unstable
    clock.advance(0.5)
    assert clf.update(Reading(brpm=24.0, bpm=120.0, confidence=0.39, motion_index=0.10)) == STATE_SIGNAL_UNSTABLE

def test_boundary_brpm():
    clock = FakeClock()
    clf = SleepStateClassifier(clock=clock.now)
    
    # 20.0 ASLEEP
    clf.update(Reading(brpm=20.0, bpm=120.0, confidence=0.90, motion_index=0.10))
    clock.advance(0.5)
    assert clf.update(Reading(brpm=20.0, bpm=120.0, confidence=0.90, motion_index=0.10)) == STATE_ASLEEP
    
    # 19.9 is DROWSY
    clock.advance(0.5)
    clf.update(Reading(brpm=19.9, bpm=120.0, confidence=0.90, motion_index=0.10))
    clock.advance(0.5)
    assert clf.update(Reading(brpm=19.9, bpm=120.0, confidence=0.90, motion_index=0.10)) == STATE_DROWSY
    
    # Reset to ASLEEP
    clock.advance(0.5)
    clf.update(Reading(brpm=24.0, bpm=120.0, confidence=0.90, motion_index=0.10))
    clock.advance(0.5)
    clf.update(Reading(brpm=24.0, bpm=120.0, confidence=0.90, motion_index=0.10))
    
    # 30.0 ASLEEP
    clock.advance(0.5)
    clf.update(Reading(brpm=30.0, bpm=120.0, confidence=0.90, motion_index=0.10))
    clock.advance(0.5)
    assert clf.update(Reading(brpm=30.0, bpm=120.0, confidence=0.90, motion_index=0.10)) == STATE_ASLEEP
    
    # 30.1 is RESTLESS (spike from 24, but even from 30, it is > 30 so it's a spike/restless)
    # Wait, the spec says "19.9/30.1 not". Let's check. 
    # If BrPM > 30, it might be RESTLESS or AWAKE.
    clock.advance(0.5)
    clf.update(Reading(brpm=30.1, bpm=120.0, confidence=0.90, motion_index=0.10))
    clock.advance(0.5)
    assert clf.update(Reading(brpm=30.1, bpm=120.0, confidence=0.90, motion_index=0.10)) != STATE_ASLEEP

def test_boundary_spike():
    # Exactly 25% spike (24.0 * 1.25 = 30.0) -> not RESTLESS
    clock = FakeClock()
    clf = SleepStateClassifier(clock=clock.now)
    clf.update(Reading(brpm=24.0, bpm=120.0, confidence=0.90, motion_index=0.10))
    clock.advance(0.5)
    clf.update(Reading(brpm=24.0, bpm=120.0, confidence=0.90, motion_index=0.10))
    
    clock.advance(0.5)
    clf.update(Reading(brpm=30.0, bpm=120.0, confidence=0.90, motion_index=0.10))
    clock.advance(0.5)
    assert clf.update(Reading(brpm=30.0, bpm=120.0, confidence=0.90, motion_index=0.10)) == STATE_ASLEEP
    
    # Just over 25% (30.0001) -> RESTLESS
    clock2 = FakeClock()
    clf2 = SleepStateClassifier(clock=clock2.now)
    clf2.update(Reading(brpm=24.0, bpm=120.0, confidence=0.90, motion_index=0.10))
    clock2.advance(0.5)
    clf2.update(Reading(brpm=24.0, bpm=120.0, confidence=0.90, motion_index=0.10))
    
    clock2.advance(0.5)
    clf2.update(Reading(brpm=30.0001, bpm=120.0, confidence=0.90, motion_index=0.10))
    clock2.advance(0.5)
    assert clf2.update(Reading(brpm=30.0001, bpm=120.0, confidence=0.90, motion_index=0.10)) == STATE_RESTLESS

def test_boundary_motion():
    clock = FakeClock()
    clf = SleepStateClassifier(clock=clock.now)
    
    # Establish baseline asleep
    clf.update(Reading(brpm=24.0, bpm=120.0, confidence=0.90, motion_index=0.10))
    clock.advance(0.5)
    clf.update(Reading(brpm=24.0, bpm=120.0, confidence=0.90, motion_index=0.10))
    
    # Motion 0.60 -> DROWSY (because it is < 0.85 and <= 0.60, but not < 0.30)
    clock.advance(0.5)
    clf.update(Reading(brpm=24.0, bpm=120.0, confidence=0.90, motion_index=0.60))
    clock.advance(0.5)
    assert clf.update(Reading(brpm=24.0, bpm=120.0, confidence=0.90, motion_index=0.60)) == STATE_DROWSY
    
    # Motion 0.61 -> RESTLESS
    clock.advance(0.5)
    clf.update(Reading(brpm=24.0, bpm=120.0, confidence=0.90, motion_index=0.61))
    clock.advance(0.5)
    assert clf.update(Reading(brpm=24.0, bpm=120.0, confidence=0.90, motion_index=0.61)) == STATE_RESTLESS
    
    # Reset to asleep
    clock.advance(0.5)
    clf.update(Reading(brpm=24.0, bpm=120.0, confidence=0.90, motion_index=0.10))
    clock.advance(0.5)
    clf.update(Reading(brpm=24.0, bpm=120.0, confidence=0.90, motion_index=0.10))
    
    # Motion 0.85 -> RESTLESS (<= 0.85)
    clock.advance(0.5)
    clf.update(Reading(brpm=24.0, bpm=120.0, confidence=0.90, motion_index=0.85))
    clock.advance(0.5)
    assert clf.update(Reading(brpm=24.0, bpm=120.0, confidence=0.90, motion_index=0.85)) == STATE_RESTLESS
    
    # Motion 0.86 -> AWAKE
    clock.advance(0.5)
    clf.update(Reading(brpm=24.0, bpm=120.0, confidence=0.90, motion_index=0.86))
    clock.advance(0.5)
    assert clf.update(Reading(brpm=24.0, bpm=120.0, confidence=0.90, motion_index=0.86)) == STATE_AWAKE

def test_boundary_baseline_fallback():
    clock = FakeClock()
    clf = SleepStateClassifier(clock=clock.now)
    
    # If no reading in 20-30 range, baseline might be fallback or None initially
    # Provide only readings < 20
    clf.update(Reading(brpm=18.0, bpm=120.0, confidence=0.90, motion_index=0.10))
    clock.advance(0.5)
    assert clf.update(Reading(brpm=18.0, bpm=120.0, confidence=0.90, motion_index=0.10)) == STATE_DROWSY

def test_boundary_hysteresis_ticks():
    clock = FakeClock()
    clf = SleepStateClassifier(clock=clock.now)
    
    # Need 2 ticks to switch state
    clf.update(Reading(brpm=24.0, bpm=120.0, confidence=0.90, motion_index=0.10))
    clock.advance(0.5)
    clf.update(Reading(brpm=24.0, bpm=120.0, confidence=0.90, motion_index=0.10))
    assert clf.current_state == STATE_ASLEEP
    
    # Tick 1: RESTLESS reading
    clock.advance(0.5)
    assert clf.update(Reading(brpm=24.0, bpm=120.0, confidence=0.90, motion_index=0.80)) == STATE_ASLEEP
    
    # Tick 2: RESTLESS reading
    clock.advance(0.5)
    assert clf.update(Reading(brpm=24.0, bpm=120.0, confidence=0.90, motion_index=0.80)) == STATE_RESTLESS
