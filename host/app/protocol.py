
from __future__ import annotations
import time
import uuid

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


def ready(sid: str, *, in_fmt="opus/16k/60ms", out_fmt="opus/24k/60ms",
          budget_ms=1240, vad=None) -> dict:
    return {
        "type": "ready",
        "sid": sid,
        "audio": {"in": in_fmt, "out": out_fmt},
        "budget_ms": budget_ms,
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
           announce: dict | None = None) -> dict:
    assert house in HOUSES
    msg = {"type": "result", "house": house, "reasons": reasons,
           "line": line, "latency": latency}
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
