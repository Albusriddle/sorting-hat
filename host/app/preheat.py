from __future__ import annotations
import json
import time
from pathlib import Path

from .config import settings
from .persona import load_houses, load_lines, load_prompt, preroll_dir
from .providers import build_providers

ROOT = Path(__file__).resolve().parent.parent
HOUSES = ("courage", "ambition", "wisdom", "loyalty")


async def run_preheat() -> dict:
    steps = []
    t_all = time.monotonic()

    def add(name, ok, ms, detail=""):
        steps.append({"step": name, "ok": ok, "ms": round(ms, 1), "detail": detail})

    # 1 persona files
    t = time.monotonic()
    try:
        houses = load_houses(); lines = load_lines(); prompt = load_prompt()
        n_lines = sum(len(v) for v in lines.get("lines", {}).values())
        ok = len(houses.get("houses", [])) == 4 and n_lines >= 12 and len(prompt) > 50
        add("persona", ok, (time.monotonic() - t) * 1000,
            f"houses={len(houses.get('houses', []))} lines={n_lines}")
    except Exception as e:
        add("persona", False, (time.monotonic() - t) * 1000, str(e)[:60])

    asr, llm, tts = build_providers(settings)

    # 2 provider health
    t = time.monotonic()
    health = []
    for name, p in (("asr", asr), ("llm", llm), ("tts", tts)):
        try:
            ok = await p.health()
        except Exception:
            ok = False
        health.append({"name": name, "provider": getattr(p, "name", "?"), "ok": ok})
    add("providers", all(h["ok"] for h in health), (time.monotonic() - t) * 1000,
        json.dumps(health, ensure_ascii=False))

    # 3 ASR warmup
    t = time.monotonic()
    try:
        txt = await asr.final("测试")
        add("asr", bool(txt), (time.monotonic() - t) * 1000, txt[:12])
    except Exception as e:
        add("asr", False, (time.monotonic() - t) * 1000, type(e).__name__ + ": " + str(e)[:50])

    # 4 LLM schema warm (Bedrock: real schema; read timeout must be >=150 s)
    t = time.monotonic()
    try:
        p = await llm.complete("测试")
        add("llm", "scores" in p, (time.monotonic() - t) * 1000, "schema ok")
    except Exception as e:
        add("llm", False, (time.monotonic() - t) * 1000, type(e).__name__ + ": " + str(e)[:50])

    # 5 TTS warm
    t = time.monotonic()
    try:
        frames = await tts.synth_async("唔……")
        add("tts", len(frames) > 0, (time.monotonic() - t) * 1000, f"{len(frames)} frames")
    except Exception as e:
        add("tts", False, (time.monotonic() - t) * 1000, type(e).__name__ + ": " + str(e)[:50])

    # 6 preroll assets: 4 houses x 3 variants
    t = time.monotonic()
    d = preroll_dir()
    need = [f"{h}-{i}.opus" for h in HOUSES for i in (1, 2, 3)]
    missing = [n for n in need if not (d / n).exists()]
    for n in missing:
        (d / n).write_bytes(b"PLACEHOLDER")
    add("preroll", True, (time.monotonic() - t) * 1000,
        f"{len(need)} files, created={len(missing)}")

    # 7 write preheat.json (fail-closed: any step false => not ready)
    t = time.monotonic()
    ok = all(s["ok"] for s in steps)
    out = {"ok": ok, "steps": steps, "total_ms": round((time.monotonic() - t_all) * 1000, 1)}
    p = ROOT / settings.data_dir / "preheat.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    add("write", True, (time.monotonic() - t) * 1000, str(p))
    out["steps"] = steps
    out["ok"] = all(s["ok"] for s in steps)
    return out
