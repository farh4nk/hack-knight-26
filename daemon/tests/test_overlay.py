import numpy as np
from cradleecho.overlay import draw_vitals_panel

def test_draw_vitals_panel_full_payload():
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    original_sum = frame.sum()
    
    payload = {
        "state": "ASLEEP",
        "vitals": {
            "brpm": 25.5,
            "bpm": 110.0,
            "confidence": 0.95
        },
        "motion_index": 0.1
    }
    
    draw_vitals_panel(frame, payload, sdk_hint="Everything is good", session_running=True)
    
    # Should have drawn something
    assert frame.sum() > original_sum

def test_draw_vitals_panel_none_payload():
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    # Should not raise
    draw_vitals_panel(frame, None)

def test_draw_vitals_panel_empty_dict():
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    # Should not raise
    draw_vitals_panel(frame, {})

def test_draw_vitals_panel_long_hint():
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    # Should not raise
    draw_vitals_panel(frame, {}, sdk_hint="A" * 1000)
