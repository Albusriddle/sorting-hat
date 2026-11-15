from __future__ import annotations
import asyncio
import json
import time
from pathlib import Path

from .config import settings
from .persona import load_houses, load_lines, load_prompt, preroll_dir
from .providers import MockASR, MockLLM, MockTTS

ROOT = Path(__file__).resolve().parent.parent


async def run_preheat() -> dict:
    steps = []
    t_all = time.monotonic()

    def add(name, ok, ms, detail=""):
        steps.append({"step": name, "ok": ok, "ms": round(ms, 1), "detail": detail})

    # 1 persona files
    t = time.monotonic()
    try:
        houses = load_houses(); lines = load_lines(); prompt = load_prompt()
        ok = len(houses.get("houses", [])) == 4 and len(lines.get("lines", {})) >= 4 and len(prompt) > 50
        add("persona", ok, (time.monotonic() - t) * 1000, f"houses={len(houses.get('houses', []))}")
    except Exception as e:
        add("persona", False, (time.monotonic() - t) * 1000, str(e)[:60])

    # 2 ASR
    t = time.monotonic()
    try:
        txt = await MockASR().final("测试")
        add("asr", bool(txt), (time.monotonic() - t) * 1000, txt[:12])
    except Exception as e:
        add("asr", False, (time.monotonic() - t) * 1000, str(e)[:60])

    # 3 LLM (schema warm) — in real life: Bedrock structured output, read timeout 150 s
    t = time.monotonic()
    try:
        p = await MockLLM().complete("测试")
        add("llm", "scores" in p, (time.monotonic() - t) * 1000, "schema ok")
    except Exception as e:
        add("llm", False, (time.monotonic() - t) * 1000, str(e)[:60])

    # 4 TTS
    t = time.monotonic()
    try:
        frames = MockTTS().synth("唔……")
        add("tts", len(frames) > 0, (time.monotonic() - t) * 1000, f"{len(frames)} frames")
    except Exception as e:
        add("tts", False, (time.monotonic() - t) * 1000, str(e)[:60])

    # 5 preroll assets (create placeholders on first run)
    t = time.monotonic()
    d = preroll_dir()
    need = [f"{h}-{i}.opus" for h in ("courage", "ambition", "wisdom", "loyalty") for i in (1, 2)]
    missing = [n for n in need if not (d / n).exists()]
    for n in missing:
        (d / n).write_bytes(b"PLACEHOLDER")
    add("preroll", True, (time.monotonic() - t) * 1000,
        f"{len(need)} files, created={len(missing)}")

    # 6 write preheat.json
    t = time.monotonic()
    all_ok = all(s["ok"] for s in steps)
    out = {"ok": all_ok, "steps": steps, "total_ms": round((time.monotonic() - t_all) * 1000, 1)}
    p = ROOT / settings.data_dir / "preheat.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    add("write", True, (time.monotonic() - t) * 1000, str(p))
    out["steps"] = steps
    out["ok"] = all(s["ok"] for s in steps)
    return out
