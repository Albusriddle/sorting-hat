
from __future__ import annotations
import time
from collections import deque
from dataclasses import dataclass, field


@dataclass
class AppState:
    started_at: float = field(default_factory=time.time)
    halt: str = "none"                     # none | halt_new | stop_all
    recent_houses: deque = field(default_factory=lambda: deque(maxlen=3))
    last_stats: dict = field(default_factory=dict)
    sessions: int = 0
    errors: int = 0
    config: dict = field(default_factory=dict)

    def snapshot(self) -> dict:
        return {
            "uptime_s": round(time.time() - self.started_at, 1),
            "halt": self.halt,
            "recent_houses": list(self.recent_houses),
            "sessions": self.sessions,
            "errors": self.errors,
            "last": self.last_stats,
            "config": self.config,
        }


STATE = AppState()
