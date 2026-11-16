
from __future__ import annotations
import time
import uuid

from .config import settings

PROTOCOL = "sortinghat.voice.v1"
HOUSES = ("courage", "ambition", "wisdom", "loyalty")

ERRORS = {
    "auth_failed", "session_expired", "rate_limited",
    "bad_frame", "asr_timeout", "llm_timeout", "tts_timeout",
    "clock_skew", "upstream_5xx", "protocol_unsupported",
}


def now_ms() -> int:
    return int(time.time() * 1000)


def new_sid() -> str:
    return "s-" + uuid.uuid4().hex[:8]


def ready(sid: str, *, in_fmt=None, out_fmt=None, budget_ms=None, vad=None) -> dict:
    # 实测：上行 20 ms / 16 kHz；下行 60 ms / 16 kHz。别再报 24k。
    return {
        "type": "ready",
        "sid": sid,
        "proto": 1,
        "audio": {
            "in": in_fmt or "pcm16|opus/16000/20ms",
            "out": out_fmt or "pcm16/16000/60ms",
        },
        "budget_ms": budget_ms if budget_ms is not None else settings.budget_ms,
        "server_time": now_ms(),
        "vad": vad or {"tail_ms": 300, "min_speech_ms": 200},
    }


def error(code: str, degrade: str = "", fatal: bool = False) -> dict:
    assert code in ERRORS, f"unknown error code: {code}"
    return {"type": "error", "code": code, "degrade": degrade, "fatal": fatal}


def tts(state: str, seg: int = 0, text: str = "") -> dict:
    msg = {"type": "tts", "state": state, "seg": seg}
    if text:
        msg["text"] = text
    return msg


def result(house: str, reasons: list[str], line: str, latency: dict,
           scores: dict | None = None, announce: dict | None = None) -> dict:
    assert house in HOUSES
    msg = {"type": "result", "house": house, "reasons": reasons,
           "line": line, "latency": latency}
    if scores:
        msg["scores"] = scores
    if announce:
        msg["announce"] = announce
    return msg


def bye(reason: str, dev_ts: dict | None = None) -> dict:
    msg = {"type": "bye", "reason": reason}
    if dev_ts:
        msg["dev_ts"] = dev_ts
    return msg


def audio_frame(seq: int, payload: bytes) -> bytes:
    return b"\x02" + int(seq).to_bytes(4, "big") + payload
