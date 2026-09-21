"""Tests for application.backend.core configuration."""

from application.backend.core.config import settings


def test_settings_initialization():
    assert settings.app_name == "Enterprise Policy Assistant (HR-207)"
    assert settings.version == "2.0.0"
    assert settings.embedding_model == "BAAI/bge-small-en-v1.5"
    assert settings.default_top_k == 5
    assert settings.max_allowed_vacation_carryover == 20
    assert settings.base_dir.exists()
