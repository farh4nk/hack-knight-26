import time
import numpy as np
import pytest
import cv2
from cradleecho.facegate import FaceGate

class FakeClock:
    def __init__(self):
        self.time = 0.0
    def __call__(self):
        return self.time
    def advance(self, secs):
        self.time += secs

def test_facegate_no_face_never_starts():
    clock = FakeClock()
    detector_calls = [0]
    def no_face_detector(gray):
        detector_calls[0] += 1
        return []

    gate = FaceGate(detector=no_face_detector, clock=clock)
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    
    assert not gate.update(frame)
    assert gate.reason == "no_face"

    clock.advance(3.0)
    assert not gate.update(frame)
    assert gate.reason == "no_face"

def test_facegate_ok_face():
    clock = FakeClock()
    # Mocking at scaled size (320x240)
    def ok_detector(gray):
        # 320 * 0.15 = 48, so face height 50 is big enough
        # center_x = 160. Within 320*0.35=112 of center -> ok.
        # chest_room = 1.0 -> 100 + 50 + 50 <= 240 (200 <= 240)
        return [(135, 100, 50, 50)]

    gate = FaceGate(detector=ok_detector, clock=clock, chest_room=1.0)
    frame = np.zeros((480, 640, 3), dtype=np.uint8)

    assert not gate.update(frame) # < start_after_s
    assert gate.reason == "ok"
    
    clock.advance(1.0)
    assert not gate.update(frame)
    
    clock.advance(1.1) # total 2.1s
    assert gate.update(frame)

def test_facegate_flapping():
    clock = FakeClock()
    faces = [[135, 100, 50, 50]]
    def detector(gray):
        return faces

    gate = FaceGate(detector=detector, clock=clock, chest_room=1.0)
    frame = np.zeros((480, 640, 3), dtype=np.uint8)

    gate.update(frame) # Sets state to ok at t=0

    clock.advance(2.1)
    assert gate.update(frame) # Active
    
    # Not ok for 5 seconds (shorter than stop_after_s=10)
    faces.clear()
    clock.advance(0.25)
    gate.update(frame) # Register change
    clock.advance(4.75)
    assert gate.update(frame) # still true!
    
    # Back to ok
    faces.append([135, 100, 50, 50])
    clock.advance(0.25)
    gate.update(frame) # Register change
    clock.advance(0.75)
    assert gate.update(frame)

    # Not ok for >= 10s
    faces.clear()
    clock.advance(0.25)
    gate.update(frame) # Register change
    clock.advance(10.0)
    assert not gate.update(frame)

def test_facegate_rejection_reasons():
    clock = FakeClock()
    faces_list = []
    def detector(gray):
        return faces_list

    gate = FaceGate(detector=detector, clock=clock, chest_room=1.0)
    frame = np.zeros((480, 640, 3), dtype=np.uint8)

    # Multiple faces
    faces_list = [(135, 100, 50, 50), (10, 10, 50, 50)]
    gate.update(frame)
    assert gate.reason == "multiple_faces"

    # Too small
    clock.advance(1.0)
    faces_list = [(135, 100, 10, 10)]
    gate.update(frame)
    assert gate.reason == "too_small"

    # Off center
    clock.advance(1.0)
    faces_list = [(10, 100, 50, 50)]
    gate.update(frame)
    assert gate.reason == "off_center"

    # No chest room
    clock.advance(1.0)
    faces_list = [(135, 200, 50, 50)]
    gate.update(frame)
    assert gate.reason == "no_chest_room"

def test_facegate_throttling():
    clock = FakeClock()
    calls = [0]
    def detector(gray):
        calls[0] += 1
        return []
    
    gate = FaceGate(detector=detector, detect_fps=5.0, clock=clock)
    frame = np.zeros((480, 640, 3), dtype=np.uint8)

    gate.update(frame)
    gate.update(frame)
    assert calls[0] == 1

    clock.advance(0.25)
    gate.update(frame)
    assert calls[0] == 2

def test_facegate_default_cascade_is_real():
    """Uses the real bundled Haar cascade (no monkeypatching): loads, finds nothing in a blank frame."""
    if not hasattr(cv2, "CascadeClassifier") or not hasattr(cv2, "data") or not hasattr(cv2.data, "haarcascades"):
        pytest.skip("cv2.CascadeClassifier not available in this OpenCV build")
    cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    assert not cascade.empty()

    gate = FaceGate()
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    assert gate.update(frame) is False
    assert gate.reason == "no_face"

def test_facegate_draw_overlay():
    clock = FakeClock()
    def ok_detector(gray):
        return [(135, 100, 50, 50)]

    gate = FaceGate(detector=ok_detector, clock=clock, chest_room=1.0)
    frame = np.zeros((480, 640, 3), dtype=np.uint8)

    # Before update, doesn't raise
    gate.draw_overlay(frame)
    
    # After update
    gate.update(frame)
    
    frame_copy = frame.copy()
    gate.draw_overlay(frame_copy)
    
    # Check pixels of blank frame changed
    assert not np.array_equal(frame, frame_copy)
    
    # Check green for ok
    assert gate.reason == "ok"
    has_green = np.any(np.all(frame_copy == [0, 255, 0], axis=-1))
    assert has_green

    # Now make it not ok
    def not_ok_detector(gray):
        return [(10, 10, 50, 50)]
    gate.detector = not_ok_detector
    clock.advance(0.25)
    gate.update(frame)
    assert gate.reason != "ok"

    frame_copy2 = frame.copy()
    gate.draw_overlay(frame_copy2)
    has_orange = np.any(np.all(frame_copy2 == [0, 165, 255], axis=-1))
    assert has_orange

def test_facegate_progress():
    clock = FakeClock()
    def ok_detector(gray):
        return [(135, 100, 50, 50)]
    def no_face_detector(gray):
        return []

    gate = FaceGate(detector=ok_detector, clock=clock, chest_room=1.0)
    frame = np.zeros((480, 640, 3), dtype=np.uint8)

    # start hysteresis
    gate.update(frame)
    assert gate.reason == "ok"
    assert not gate.is_active
    clock.advance(1.2)
    assert "arming 1.2/2.0s" in gate.progress()

    # become active
    clock.advance(1.0)
    gate.update(frame)
    assert gate.is_active

    # stop hysteresis
    gate.detector = no_face_detector
    clock.advance(0.25)
    gate.update(frame)
    assert gate.reason == "no_face"
    assert gate.is_active
    clock.advance(3.0)
    assert "closing 3.0/10.0s" in gate.progress()



def test_facegate_stub_detector_room_ratio():
    clock = FakeClock()
    def detector(gray):
        return [(135, 115, 50, 50)]

    gate_new = FaceGate(detector=detector, clock=clock)
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    gate_new.update(frame)
    assert gate_new.reason == "no_chest_room"
    assert gate_new.last_room_ratio == 1.5
    assert np.isclose(gate_new.last_face_frac, 50 / 240)

    gate_old = FaceGate(detector=detector, clock=clock, chest_room=1.0)
    gate_old.update(frame)
    assert gate_old.reason == "ok"
    assert gate_old.last_room_ratio == 1.5

def test_config_defaults(monkeypatch):
    from cradleecho.config import Settings
    s = Settings(cradleecho_source="mock")
    assert s.gate_chest_room == 1.75
    assert s.gate_min_face_frac == 0.15

    monkeypatch.setenv("CRADLEECHO_GATE_CHEST_ROOM", "2.5")
    monkeypatch.setenv("CRADLEECHO_GATE_MIN_FACE", "0.2")
    s2 = Settings(cradleecho_source="mock")
    assert s2.gate_chest_room == 2.5
    assert s2.gate_min_face_frac == 0.2
