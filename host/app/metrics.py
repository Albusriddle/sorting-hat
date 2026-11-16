
from __future__ import annotations
import json
import time
from pathlib import Path

from .config import settings

ROOT = Path(__file__).resolve().parent.parent


def _log_path() -> Path:
    return ROOT / settings.data_dir / "sessions.jsonl"


def record(row: dict) -> None:
    path = _log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    row = {"recv_wall": int(time.time() * 1000), **row}
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def tail(n: int = 20) -> list[dict]:
    path = _log_path()
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()[-n:]
    return [json.loads(x) for x in lines if x.strip()]
