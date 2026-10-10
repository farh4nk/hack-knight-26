import pytest
from pydantic import SecretStr

from cradleecho.config import Settings
from cradleecho.main import build_source
from cradleecho.sources.presage import PresageVitalsSource

def test_settings_repr_str():
    s = Settings(presage_api_key="super_secret_key_123")
    assert "super_secret_key_123" not in repr(s)
    assert "super_secret_key_123" not in str(s)

def test_build_source_presage_missing_key(monkeypatch):
    from cradleecho.main import settings
    from cradleecho.sources.mock import MockVitalsSource
    monkeypatch.setattr(settings, "source", "presage")
    monkeypatch.setattr(settings, "presage_api_key", None)
    
    src = build_source()
    assert isinstance(src, MockVitalsSource)

def test_build_source_presage_with_key(monkeypatch):
    from cradleecho.main import settings
    monkeypatch.setattr(settings, "source", "presage")
    monkeypatch.setattr(settings, "presage_api_key", SecretStr("fake"))
    
    src = build_source()
    assert isinstance(src, PresageVitalsSource)
