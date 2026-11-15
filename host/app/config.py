
from __future__ import annotations
import os
from dataclasses import dataclass, field


def _env(name: str, default: str) -> str:
    return os.getenv(name, default)


@dataclass
class Settings:
    """All runtime knobs. Every value is overridable by env (see .env.example)."""
    host: str = _env("HOST_BIND", "0.0.0.0")
    port: int = int(_env("PORT", "8443"))
    admin_port: int = int(_env("ADMIN_PORT", "8080"))
    admin_token: str = _env("ADMIN_TOKEN", "dev-token")
    data_dir: str = _env("DATA_DIR", "var")

    # session
    session_max_ms: int = int(_env("SESSION_MAX_MS", "120000"))
    silence_ms: int = int(_env("SILENCE_MS", "6500"))
    silence_bye_ms: int = int(_env("SILENCE_BYE_MS", "15000"))

    # soft timeouts (budget from the design doc)
    asr_timeout_ms: int = int(_env("ASR_TIMEOUT_MS", "600"))
    llm_timeout_ms: int = int(_env("LLM_TIMEOUT_MS", "900"))
    tts_timeout_ms: int = int(_env("TTS_TIMEOUT_MS", "800"))

    # judge
    max_share: float = float(_env("MAX_SHARE", "0.40"))
    recent3_penalty: float = float(_env("RECENT3_PENALTY", "0.85"))

    # providers: "mock" | "aws" | "aliyun"
    asr_provider: str = _env("ASR_PROVIDER", "mock")
    llm_provider: str = _env("LLM_PROVIDER", "mock")
    tts_provider: str = _env("TTS_PROVIDER", "mock")
    bedrock_model_id: str = _env("BEDROCK_MODEL_ID", "anthropic.claude-haiku")
    nemotron_enabled: bool = _env("NEMOTRON_ENABLED", "0") in ("1", "true", "yes")


settings = Settings()
