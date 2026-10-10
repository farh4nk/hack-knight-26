"""Tests for night vision enhancement and API."""

import asyncio
import numpy as np
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch

from cradleecho.camera import Camera, enhance_low_light, NIGHT_VISION_MODES
from cradleecho.classifier import SleepStateClassifier
from cradleecho.main import create_app
from cradleecho.sources.mock import MockVitalsSource


def test_enhance_low_light_raises_brightness():
    """Test that enhance_low_light increases mean brightness of dark frame."""
    # Create a dark synthetic frame (mean ~30)
    dark_frame = np.full((480, 640, 3), 30, dtype=np.uint8)
    # Add some texture so CLAHE has something to work with
    dark_frame[::10, ::10] = 50
    
    original_mean = float(np.mean(dark_frame))
    enhanced = enhance_low_light(dark_frame, brightness=original_mean)
    
    enhanced_mean = float(np.mean(enhanced))
    assert enhanced_mean > original_mean, f"Expected brightness increase: {original_mean} -> {enhanced_mean}"
    assert enhanced.shape == dark_frame.shape
    assert enhanced.dtype == dark_frame.dtype


def test_enhance_low_light_preserves_shape_dtype():
    """Test that enhance_low_light preserves shape and dtype."""
    frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
    enhanced = enhance_low_light(frame, brightness=100.0)
    
    assert enhanced.shape == frame.shape
    assert enhanced.dtype == frame.dtype


def test_enhance_low_light_bright_frame_minimal_change():
    """Test that bright frames get minimal enhancement."""
    bright_frame = np.full((480, 640, 3), 200, dtype=np.uint8)
    original_mean = float(np.mean(bright_frame))
    enhanced = enhance_low_light(bright_frame, brightness=original_mean)
    
    enhanced_mean = float(np.mean(enhanced))
    # Bright frames should not be dramatically changed
    assert abs(enhanced_mean - original_mean) < 30


@pytest.fixture
def test_app():
    camera = Camera(device="none")
    source = MockVitalsSource(seed=42)
    classifier = SleepStateClassifier()
    app = create_app(camera=camera, source=source, classifier=classifier)
    return app, camera


def test_night_vision_get_default_mode(test_app):
    """Test GET /api/night-vision returns default mode."""
    app, camera = test_app
    
    with TestClient(app) as client:
        response = client.get("/api/night-vision")
        assert response.status_code == 200
        data = response.json()
        assert data["mode"] == "AUTO"
        assert "active" in data
        assert isinstance(data["active"], bool)


def test_night_vision_post_valid_modes(test_app):
    """Test POST /api/night-vision accepts valid modes."""
    app, camera = test_app
    
    with TestClient(app) as client:
        for mode in ["OFF", "AUTO", "ON"]:
            response = client.post("/api/night-vision", json={"mode": mode})
            assert response.status_code == 200
            data = response.json()
            assert data["mode"] == mode
            assert "active" in data
            
            # Verify camera state updated
            assert camera.get_night_vision_mode() == mode


def test_night_vision_post_invalid_mode_422(test_app):
    """Test POST /api/night-vision rejects invalid mode with 422."""
    app, camera = test_app
    
    with TestClient(app) as client:
        response = client.post("/api/night-vision", json={"mode": "INVALID"})
        assert response.status_code == 422


def test_night_vision_hysteresis_on_at_50_stays_on_at_70_off_at_85(test_app):
    """Test AUTO mode hysteresis: on at 50, stays on at 70, off at 85."""
    app, camera = test_app
    
    # Set to AUTO mode
    camera.set_night_vision_mode("AUTO")
    
    # Simulate brightness readings by directly manipulating internal state
    with camera._lock:
        camera._brightness_ema = 50.0
        camera._night_on_below = 60.0
        camera._night_off_above = 80.0
        camera._enhancing = False
    
    # Manually trigger the hysteresis logic (simulate a frame processing cycle)
    # Since we can't easily inject frames, test the logic directly
    camera._update_enhancing_state()
    
    assert camera.is_enhancing() is True  # Should turn ON at 50 (< 60)
    
    # Now brightness rises to 70 - should STAY ON (hysteresis)
    with camera._lock:
        camera._brightness_ema = 70.0
    camera._update_enhancing_state()
    assert camera.is_enhancing() is True  # Should stay ON at 70 (< 80)
    
    # Now brightness rises to 85 - should turn OFF
    with camera._lock:
        camera._brightness_ema = 85.0
    camera._update_enhancing_state()
    assert camera.is_enhancing() is False  # Should turn OFF at 85 (> 80)


def test_night_vision_off_mode_never_enhances(test_app):
    """Test OFF mode never enhances."""
    app, camera = test_app
    
    camera.set_night_vision_mode("OFF")
    
    with camera._lock:
        camera._brightness_ema = 10.0  # Very dark
    camera._update_enhancing_state()
    
    assert camera.is_enhancing() is False


def test_night_vision_on_mode_always_enhances(test_app):
    """Test ON mode always enhances."""
    app, camera = test_app
    
    camera.set_night_vision_mode("ON")
    
    with camera._lock:
        camera._brightness_ema = 200.0  # Very bright
    camera._update_enhancing_state()
    
    assert camera.is_enhancing() is True


def test_camera_get_set_night_vision_mode(test_app):
    """Test camera night vision mode getter/setter."""
    app, camera = test_app
    
    # Default
    assert camera.get_night_vision_mode() in NIGHT_VISION_MODES
    
    # Set each mode
    for mode in ["OFF", "AUTO", "ON"]:
        camera.set_night_vision_mode(mode)
        assert camera.get_night_vision_mode() == mode
    
    # Invalid mode raises
    with pytest.raises(ValueError):
        camera.set_night_vision_mode("INVALID")


def test_camera_is_enhancing_property(test_app):
    """Test camera is_enhancing property."""
    app, camera = test_app
    
    camera.set_night_vision_mode("OFF")
    assert camera.is_enhancing() is False
    
    camera.set_night_vision_mode("ON")
    assert camera.is_enhancing() is True