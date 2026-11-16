
from __future__ import annotations
import time
from collections import deque
from dataclasses import dataclass, field

from .config import settings


@dataclass
class AppState:
    started_at: float = field(default_factory=time.time)
    halt: str = "none"                     # none | halt_new | stop_all
    last_stats: dict = field(default_factory=dict)
    last_audio: dict = field(default_factory=dict)
    session_stats: dict = field(default_factory=dict)
    session_audio: dict = field(default_factory=dict)
    sessions: int = 0
    errors: int = 0
    config: dict = field(default_factory=dict)
    _recent: dict = field(default_factory=dict)

    def recent_for(self, sid: str) -> deque:
        key = sid or "_"
        if key not in self._recent:
            self._recent[key] = deque(maxlen=settings.history_window)
        return self._recent[key]

    def set_stats(self, sid: str, stats: dict) -> None:
        key = sid or "_"
        self.session_stats[key] = stats
        self.last_stats = stats

    def set_audio(self, sid: str, audio: dict) -> None:
        key = sid or "_"
        self.session_audio[key] = audio
        self.last_audio = audio

    def drop_sid(self, sid: str) -> None:
        key = sid or "_"
        self._recent.pop(key, None)
        self.session_stats.pop(key, None)
        self.session_audio.pop(key, None)

    def snapshot(self) -> dict:
        return {
            "uptime_s": round(time.time() - self.started_at, 1),
            "halt": self.halt,
            "recent_houses": list(self._recent.get("_", [])),
            "sessions": self.sessions,
            "errors": self.errors,
            "last": self.last_stats,
            "audio": self.last_audio,
            "config": self.config,
        }


STATE = AppState()
