
from __future__ import annotations
import hashlib
from functools import lru_cache
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parent.parent
PERSONA = ROOT / "persona"


def load_houses() -> dict:
    return yaml.safe_load((PERSONA / "houses.yaml").read_text(encoding="utf-8"))


def load_lines() -> dict:
    return yaml.safe_load((PERSONA / "lines.yaml").read_text(encoding="utf-8"))


def load_prompt() -> str:
    return (PERSONA / "prompt.md").read_text(encoding="utf-8")


def preroll_dir() -> Path:
    p = ROOT / "assets" / "preroll"
    p.mkdir(parents=True, exist_ok=True)
    return p


def sha256_of(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


@lru_cache(maxsize=1)
def _lines() -> dict:
    return load_lines().get("lines", {})


def pick_announcement(house: str, n: int) -> tuple[str, int]:
    """Deterministic rotation over the pre-recorded announcement variants."""
    opts = _lines().get(house) or []
    if not opts:
        return ("", 0)
    v = n % len(opts)
    return (opts[v], v)
