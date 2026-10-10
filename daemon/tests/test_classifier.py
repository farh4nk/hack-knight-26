"""Unit tests for the pure sleep state classifier."""

from cradleecho.classifier import (
    STATE_ASLEEP,
    STATE_AWAKE,
    STATE_DROWSY,
    STATE_RESTLESS,
    STATE_SIGNAL_UNSTABLE,
    ClassifierConfig,
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


# Short hold so tests don't need minutes of fake time; the default (20 s) is covered separately.
CFG = ClassifierConfig(asleep_hold_s=10.0)


def reading(brpm: float, motion: float, conf: float = 0.90, bpm: float = 118.0) -> Reading:
    return Reading(brpm=brpm, bpm=bpm, confidence=conf, motion_index=motion)


def make(config: ClassifierConfig = CFG):
    clock = FakeClock()
    return clock, SleepStateClassifier(clock=clock.now, config=config)


def feed(clf, clock, r: Reading, seconds: float, step: float = 0.5) -> str:
    """Feed the same reading every `step` seconds for `seconds`; return the final state."""
    state = clf.current_state
    for _ in range(int(round(seconds / step))):
        clock.advance(step)
        state = clf.update(r)
    return state


# ---- initial / unstable -------------------------------------------------------------------


def test_state_before_any_reading_is_unstable_not_asleep():
    _, clf = make()
    assert clf.current_state == STATE_SIGNAL_UNSTABLE


def test_presage_warmup_reading_is_unstable_not_drowsy():
    # Presage reports confidence 1.0 with breathing 0 while it warms up.
    clock, clf = make()
    assert clf.update(reading(brpm=0.0, motion=0.02, conf=1.0)) == STATE_SIGNAL_UNSTABLE


def test_signal_unstable_switches_immediately():
    clock, clf = make()
    feed(clf, clock, reading(26, 0.03), 12)
    clock.advance(0.5)
    assert clf.update(reading(26, 0.03, conf=0.25)) == STATE_SIGNAL_UNSTABLE


def test_recovery_from_signal_unstable_requires_hysteresis():
    clock, clf = make()
    clf.update(reading(0.0, 0.0, conf=0.10))
    assert clf.current_state == STATE_SIGNAL_UNSTABLE
    clock.advance(0.5)
    assert clf.update(reading(26, 0.03)) == STATE_SIGNAL_UNSTABLE  # one good tick isn't enough
    clock.advance(0.5)
    assert clf.update(reading(26, 0.03)) != STATE_SIGNAL_UNSTABLE


def test_confidence_boundary():
    clock, clf = make()
    assert clf.evaluate_candidate(reading(26, 0.03, conf=0.40), 26.0) != STATE_SIGNAL_UNSTABLE
    assert clf.evaluate_candidate(reading(26, 0.03, conf=0.39), 26.0) == STATE_SIGNAL_UNSTABLE


# ---- awake adults must not read as asleep (the reported bug) ------------------------------


def test_awake_adult_sitting_still_is_awake_not_drowsy_or_asleep():
    # Adult at rest: ~15 breaths/min, almost no movement, heart rate 74.
    clock, clf = make(ClassifierConfig())  # production defaults
    state = feed(clf, clock, reading(15, 0.02, bpm=74), 60)
    assert state == STATE_AWAKE


def test_breathing_below_the_sleep_range_is_awake_even_when_perfectly_still():
    clock, clf = make()
    assert feed(clf, clock, reading(18, 0.0), 30) == STATE_AWAKE


def test_breathing_above_the_sleep_range_is_awake():
    clock, clf = make()
    assert feed(clf, clock, reading(46, 0.03), 5) == STATE_AWAKE


# ---- asleep has to be earned --------------------------------------------------------------


def test_calm_sleeping_breathing_is_drowsy_until_held_then_asleep():
    clock, clf = make()
    assert feed(clf, clock, reading(26, 0.03), 5) == STATE_DROWSY  # settling, not asleep yet
    assert feed(clf, clock, reading(26, 0.03), 8) == STATE_ASLEEP  # held past asleep_hold_s


def test_default_hold_is_twenty_seconds():
    clock, clf = make(ClassifierConfig())
    assert feed(clf, clock, reading(26, 0.03), 15) == STATE_DROWSY
    assert feed(clf, clock, reading(26, 0.03), 8) == STATE_ASLEEP


def test_a_brief_stir_resets_the_asleep_hold():
    clock, clf = make()
    assert feed(clf, clock, reading(26, 0.03), 14) == STATE_ASLEEP
    assert feed(clf, clock, reading(26, 0.60), 1.5) == STATE_AWAKE  # big movement
    # Calm again: back to settling, must not jump straight to asleep.
    assert feed(clf, clock, reading(26, 0.03), 5) == STATE_DROWSY
    assert feed(clf, clock, reading(26, 0.03), 8) == STATE_ASLEEP


def test_small_movement_while_settling_does_not_reset_the_hold():
    clock, clf = make()
    feed(clf, clock, reading(26, 0.03), 6)
    feed(clf, clock, reading(26, 0.14), 1.5)  # drowsy-level movement (between calm and restless)
    assert feed(clf, clock, reading(26, 0.03), 5) == STATE_ASLEEP


# ---- movement thresholds ------------------------------------------------------------------


def test_motion_bands():
    clock, clf = make()
    cfg = clf.config
    r = lambda m: reading(26, m)  # noqa: E731
    assert clf.evaluate_candidate(r(cfg.calm_motion - 0.01), 26.0) == STATE_ASLEEP
    assert clf.evaluate_candidate(r(cfg.calm_motion), 26.0) == STATE_DROWSY
    assert clf.evaluate_candidate(r(cfg.restless_motion - 0.01), 26.0) == STATE_DROWSY
    assert clf.evaluate_candidate(r(cfg.restless_motion), 26.0) == STATE_RESTLESS
    assert clf.evaluate_candidate(r(cfg.awake_motion - 0.01), 26.0) == STATE_RESTLESS
    assert clf.evaluate_candidate(r(cfg.awake_motion), 26.0) == STATE_AWAKE


def test_moving_while_awake_is_awake_not_restless():
    # Shifting in a chair: moderate movement but breathing is outside the sleeping range.
    clock, clf = make()
    assert feed(clf, clock, reading(17, 0.25), 5) == STATE_AWAKE


def test_motion_transitions_need_two_ticks():
    clock, clf = make()
    feed(clf, clock, reading(26, 0.03), 14)
    assert clf.current_state == STATE_ASLEEP
    clock.advance(0.5)
    assert clf.update(reading(26, 0.30)) == STATE_ASLEEP  # first tick: pending
    clock.advance(0.5)
    assert clf.update(reading(26, 0.30)) == STATE_RESTLESS


# ---- breathing spike ----------------------------------------------------------------------


def test_breathing_spike_above_sleep_baseline_is_restless():
    clock, clf = make()
    feed(clf, clock, reading(26, 0.03), 8)  # establishes a sleep baseline of 26
    assert feed(clf, clock, reading(34, 0.03), 1.0) == STATE_RESTLESS  # 34 > 26 * 1.25


def test_no_spike_rule_without_a_sleep_baseline():
    # An adult at 15 then 19 breaths/min has no in-range baseline; this must not read as restless.
    clock, clf = make()
    feed(clf, clock, reading(15, 0.02), 8)
    assert feed(clf, clock, reading(19, 0.02), 1.0) == STATE_AWAKE


def test_spike_boundary_is_strictly_greater_than_125_percent():
    clock, clf = make()
    feed(clf, clock, reading(24, 0.03), 8)
    assert clf.evaluate_candidate(reading(30.0, 0.03), 24.0) != STATE_RESTLESS
    assert clf.evaluate_candidate(reading(30.1, 0.03), 24.0) == STATE_RESTLESS


# ---- sleep band ---------------------------------------------------------------------------


def test_sleep_band_edges_are_inclusive():
    cfg = ClassifierConfig()
    assert cfg.in_sleep_band(cfg.asleep_brpm_min)
    assert cfg.in_sleep_band(cfg.asleep_brpm_max)
    assert not cfg.in_sleep_band(cfg.asleep_brpm_min - 0.1)
    assert not cfg.in_sleep_band(cfg.asleep_brpm_max + 0.1)


def test_thresholds_are_configurable():
    # e.g. tuning for an older child or a calibration session with an adult.
    cfg = ClassifierConfig(asleep_brpm_min=10.0, asleep_brpm_max=20.0, asleep_hold_s=2.0)
    clock, clf = make(cfg)
    assert feed(clf, clock, reading(15, 0.02), 6) == STATE_ASLEEP


# ---- forced restless (demo trigger) -------------------------------------------------------


def test_force_restless_and_settle_back_to_asleep():
    clock, clf = make()
    feed(clf, clock, reading(26, 0.03), 14)
    assert clf.current_state == STATE_ASLEEP

    expiry = clf.force_restless(duration_s=15.0)
    assert clf.current_state == STATE_RESTLESS
    clock.advance(5)
    assert clf.update(reading(26, 0.03)) == STATE_RESTLESS  # calm readings are ignored while forced
    clock.advance(11)  # past expiry
    assert clock.now() > expiry

    # After the forced window the baby has to settle again before reading asleep.
    assert feed(clf, clock, reading(26, 0.03), 4) == STATE_DROWSY
    assert feed(clf, clock, reading(26, 0.03), 8) == STATE_ASLEEP
