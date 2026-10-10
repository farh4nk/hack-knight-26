"""Tests for audio capabilities endpoint."""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch

from cradleecho.camera import Camera
from cradleecho.classifier import SleepStateClassifier
from cradleecho.config import settings
from cradleecho.main import create_app
from cradleecho.sources.mock import MockVitalsSource


@pytest.fixture
def test_app():
    camera = Camera(device="none")
    source = MockVitalsSource(seed=42)
    classifier = SleepStateClassifier()
    app = create_app(camera=camera, source=source, classifier=classifier)
    return app


def test_audio_capabilities_endpoint_exists(test_app):
    """Test GET /api/audio/capabilities returns expected structure."""
    with TestClient(test_app) as client:
        response = client.get("/api/audio/capabilities")
        assert response.status_code == 200
        data = response.json()
        assert "talk" in data
        assert "listen" in data
        assert isinstance(data["talk"], bool)
        assert isinstance(data["listen"], bool)


def test_audio_capabilities_talk_true_when_aplay_exists(test_app):
    """Test talk=true when aplay or ffplay exists."""
    with patch("shutil.which") as mock_which:
        mock_which.side_effect = lambda x: "/usr/bin/aplay" if x == "aplay" else None
        
        with TestClient(test_app) as client:
            response = client.get("/api/audio/capabilities")
            assert response.status_code == 200
            assert response.json()["talk"] is True


def test_audio_capabilities_talk_true_when_ffplay_exists(test_app):
    """Test talk=true when ffplay exists (fallback)."""
    with patch("shutil.which") as mock_which:
        mock_which.side_effect = lambda x: "/usr/bin/ffplay" if x == "ffplay" else None
        
        with TestClient(test_app) as client:
            response = client.get("/api/audio/capabilities")
            assert response.status_code == 200
            assert response.json()["talk"] is True


def test_audio_capabilities_talk_false_when_no_player(test_app):
    """Test talk=false when no player binary exists."""
    with patch("shutil.which") as mock_which:
        mock_which.return_value = None
        
        with TestClient(test_app) as client:
            response = client.get("/api/audio/capabilities")
            assert response.status_code == 200
            assert response.json()["talk"] is False


def test_audio_capabilities_listen_true_when_enabled_and_arecord(test_app):
    """Test listen=true when CRADLEECHO_LISTEN=1 and arecord exists."""
    with patch("shutil.which") as mock_which:
        mock_which.side_effect = lambda x: "/usr/bin/arecord" if x == "arecord" else None
        
        # Temporarily enable listen
        original = settings.listen_enabled
        settings.listen_enabled = True
        
        try:
            with TestClient(test_app) as client:
                response = client.get("/api/audio/capabilities")
                assert response.status_code == 200
                assert response.json()["listen"] is True
        finally:
            settings.listen_enabled = original


def test_audio_capabilities_listen_false_when_disabled(test_app):
    """Test listen=false when CRADLEECHO_LISTEN=0."""
    with patch("shutil.which") as mock_which:
        mock_which.side_effect = lambda x: "/usr/bin/arecord" if x == "arecord" else None
        
        original = settings.listen_enabled
        settings.listen_enabled = False
        
        try:
            with TestClient(test_app) as client:
                response = client.get("/api/audio/capabilities")
                assert response.status_code == 200
                assert response.json()["listen"] is False
        finally:
            settings.listen_enabled = original


def test_audio_capabilities_listen_false_when_no_arecord(test_app):
    """Test listen=false when arecord not found."""
    with patch("shutil.which") as mock_which:
        mock_which.return_value = None
        
        original = settings.listen_enabled
        settings.listen_enabled = True
        
        try:
            with TestClient(test_app) as client:
                response = client.get("/api/audio/capabilities")
                assert response.status_code == 200
                assert response.json()["listen"] is False
        finally:
            settings.listen_enabled = original