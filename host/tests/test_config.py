import pytest
from app.config import Settings, validate_settings


def test_defaults_pass_validation():
    validate_settings(Settings())


def test_equal_silence_and_bye_is_rejected():
    s = Settings()
    s.silence_ms = 15000
    s.silence_bye_ms = 15000
    with pytest.raises(ValueError):
        validate_settings(s)


def test_bye_must_be_five_seconds_later():
    s = Settings()
    s.silence_ms = 8000
    s.silence_bye_ms = 12000
    with pytest.raises(ValueError):
        validate_settings(s)
