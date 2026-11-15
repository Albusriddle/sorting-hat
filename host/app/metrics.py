
from __future__ import annotations
import json
import time
from pathlib import Path
from .config import settings

LOG = Path(settings.data_dir) / "sessions.jsonl"


def record(row: dict) -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    row = {"recv_wall": int(time.time() * 1000), **row}
    with LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def tail(n: int = 20) -> list[dict]:
    if not LOG.exists():
        return []
    lines = LOG.read_text(encoding="utf-8").splitlines()[-n:]
    return [json.loads(x) for x in lines if x.strip()]
