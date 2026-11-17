
from __future__ import annotations
import os
from dataclasses import dataclass


def _env(name: str, default: str) -> str:
    return os.getenv(name, default)


def _b(name: str, default: str = "0") -> bool:
    return _env(name, default).lower() in ("1", "true", "yes", "on")


@dataclass
class Settings:
    # network
    host: str = _env("HOST_BIND", "0.0.0.0")
    port: int = int(_env("PORT", "8443"))
    admin_port: int = int(_env("ADMIN_PORT", "8080"))
    admin_token: str = _env("ADMIN_TOKEN", "dev-token")
    device_token: str = _env("DEVICE_TOKEN", "dev-token")
    data_dir: str = _env("DATA_DIR", "var")
    require_tls: bool = _b("REQUIRE_TLS", "0")
    tls_cert: str = _env("TLS_CERT", "")
    tls_key: str = _env("TLS_KEY", "")

    # session
    session_max_ms: int = int(_env("SESSION_MAX_MS", "120000"))
    silence_ms: int = int(_env("SILENCE_MS", "12000"))
    silence_bye_ms: int = int(_env("SILENCE_BYE_MS", "20000"))
    budget_ms: int = int(_env("BUDGET_MS", "1240"))
    text_max_chars: int = int(_env("TEXT_MAX_CHARS", "200"))
    tts_bridge_max_chars: int = int(_env("TTS_BRIDGE_MAX_CHARS", "40"))
    min_audio_rms: int = int(_env("MIN_AUDIO_RMS", "50"))

    # soft timeouts
    asr_timeout_ms: int = int(_env("ASR_TIMEOUT_MS", "600"))
    llm_timeout_ms: int = int(_env("LLM_TIMEOUT_MS", "900"))
    tts_timeout_ms: int = int(_env("TTS_TIMEOUT_MS", "800"))
    tts_pace_ms: int = int(_env("TTS_PACE_MS", "60"))

    # judge
    history_window: int = int(_env("HISTORY_WINDOW", "10"))
    min_history_for_balance: int = int(_env("MIN_HISTORY_FOR_BALANCE", "10"))
    max_share: float = float(_env("MAX_SHARE", "0.40"))
    recent3_penalty: float = float(_env("RECENT3_PENALTY", "0.85"))

    # providers
    asr_provider: str = _env("ASR_PROVIDER", "mock")
    llm_provider: str = _env("LLM_PROVIDER", "mock")
    tts_provider: str = _env("TTS_PROVIDER", "mock")
    bedrock_model_id: str = _env("BEDROCK_MODEL_ID", "anthropic.claude-haiku")
    nemotron_enabled: bool = _b("NEMOTRON_ENABLED", "0")
    prerecord_required: bool = _b("PRERECORD_REQUIRED", "0")


settings = Settings()


def validate_settings(s: Settings | None = None) -> None:
    """Fail fast on the silence/bye pair (联调踩过的坑)."""
    s = s or settings
    if s.silence_ms <= 0:
        raise ValueError("SILENCE_MS must be > 0")
    if s.silence_bye_ms < s.silence_ms + 5000:
        raise ValueError(
            f"SILENCE_BYE_MS({s.silence_bye_ms}) must be >= SILENCE_MS({s.silence_ms}) + 5000")
