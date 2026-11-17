
from __future__ import annotations
import json
from pathlib import Path

from fastapi import Body, FastAPI, Header, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse

from . import judge
from .config import effective, settings, validate_settings
from .metrics import tail
from .persona import load_houses, load_lines, load_prompt
from .preheat import run_preheat
from .providers import MockLLM, build_providers
from .state import STATE

admin_app = FastAPI(title="sortinghat-admin")
ROOT = Path(__file__).resolve().parent.parent


def _is_local(req: Request) -> bool:
    return req.client is not None and req.client.host in ("127.0.0.1", "::1")


def _require(token: str | None) -> None:
    if token != settings.admin_token:
        raise HTTPException(status_code=401, detail="admin token required")


def _require_or_local(req: Request, token: str | None) -> None:
    if _is_local(req):
        return
    _require(token)


@admin_app.get("/healthz")
async def healthz():
    return {"ok": True}


@admin_app.get("/readyz")
async def readyz():
    path = ROOT / settings.data_dir / "preheat.json"
    if not path.exists():
        return JSONResponse({"ok": False, "reason": "preheat not run"}, status_code=503)
    data = json.loads(path.read_text(encoding="utf-8"))
    ok = bool(data.get("ok"))
    return JSONResponse({"ok": ok, "degraded": data.get("degraded", []),
                         "preheat": data}, status_code=200 if ok else 503)


@admin_app.post("/v1/preheat")
async def preheat(x_admin_token: str | None = Header(default=None)):
    _require(x_admin_token)
    return await run_preheat()


@admin_app.post("/v1/replay")
async def replay(payload: dict = Body(default={}),
                 x_admin_token: str | None = Header(default=None)):
    _require(x_admin_token)
    text = payload.get("text") or "我最想要的是被认可，但我又不想说出来。"
    provider = "mock"
    try:
        llm = build_providers(settings)[1]
        provider = getattr(llm, "name", "mock")
        p = await llm.complete(text)
    except Exception:
        llm = MockLLM()
        provider = "mock"
        p = await llm.complete(text)
    v = judge.decide(text, p, payload.get("recent", []),
                     penalty=settings.recent3_penalty, max_share=settings.max_share,
                     min_history=settings.min_history_for_balance)
    return {"house": v["house"], "reasons": v["reasons"], "quote_ok": v["quote_ok"],
            "insufficient": v.get("insufficient", False), "provider": provider}


@admin_app.get("/v1/sessions")
async def sessions(n: int = 20, x_admin_token: str | None = Header(default=None)):
    _require(x_admin_token)
    return {"rows": tail(n)}


@admin_app.get("/stats")
async def stats(req: Request, x_admin_token: str | None = Header(default=None)):
    _require_or_local(req, x_admin_token)
    return STATE.snapshot()


@admin_app.get("/v1/metrics", response_class=PlainTextResponse)
async def metrics(req: Request, x_admin_token: str | None = Header(default=None)):
    _require_or_local(req, x_admin_token)
    s = STATE.snapshot()
    last = s.get("last") or {}
    lat = last.get("latency") or {}
    return "\n".join([
        "# HELP sortinghat_sessions_total sessions served",
        f"sortinghat_sessions_total {s['sessions']}",
        "# HELP sortinghat_errors_total protocol errors",
        f"sortinghat_errors_total {s['errors']}",
        "# HELP sortinghat_ttfc_ms last session TTFC (host side)",
        f"sortinghat_ttfc_ms {lat.get('host_ms', -1)}",
    ]) + "\n"


@admin_app.get("/v1/selfcheck")
async def selfcheck(x_admin_token: str | None = Header(default=None)):
    """一看就知道这一场跑的是什么参数（token 已掩码）。"""
    _require(x_admin_token)
    return JSONResponse({"ok": True, "effective": effective(),
                         "halt": STATE.halt, "config_overrides": STATE.config})


@admin_app.post("/v1/config")
async def config(payload: dict = Body(default={}),
                 x_admin_token: str | None = Header(default=None)):
    _require(x_admin_token)
    keys = ("max_share", "recent3_penalty", "min_history_for_balance",
            "silence_ms", "silence_bye_ms", "min_audio_rms")
    old = {k: getattr(settings, k) for k in keys}
    applied = {}
    try:
        for key in keys:
            if key in payload:
                setattr(settings, key, type(getattr(settings, key))(payload[key]))
                applied[key] = getattr(settings, key)
        validate_settings()                 # silence/bye 组合必须一起过
    except (TypeError, ValueError) as exc:
        for key, value in old.items():
            setattr(settings, key, value)
        raise HTTPException(status_code=400, detail=f"invalid config: {exc}")
    STATE.config.update(applied)
    return {"ok": True, "applied": applied}


@admin_app.post("/v1/halt")
async def halt(payload: dict = Body(default={}),
               x_admin_token: str | None = Header(default=None)):
    _require(x_admin_token)
    mode = payload.get("mode", "halt_new")
    if mode not in ("none", "halt_new", "stop_all"):
        raise HTTPException(status_code=400, detail="bad mode")
    STATE.halt = mode
    return {"ok": True, "halt": mode}


@admin_app.get("/", response_class=HTMLResponse)
async def console(req: Request, x_admin_token: str | None = Header(default=None)):
    _require_or_local(req, x_admin_token)
    return """<!doctype html><html lang="zh"><meta charset="utf-8">
<title>掂量帽 · 大屏</title>
<style>
body{background:#111;color:#eee;font:16px/1.6 -apple-system,"Microsoft YaHei",sans-serif;margin:0}
main{max-width:900px;margin:40px auto;padding:0 24px}
h1{font-size:22px;letter-spacing:.08em;color:#c9a227}
#house{font-size:64px;font-weight:700;margin:8px 0}
#reasons li{margin:6px 0;color:#ddd}
#lat{color:#888;font-size:13px;font-family:ui-monospace,Consolas,monospace}
.bar{height:6px;background:#222;border-radius:3px;overflow:hidden;margin:12px 0}
.bar i{display:block;height:100%;width:0;background:#c9a227;transition:width .3s}
</style>
<main>
  <h1>掂量帽 · 现场</h1>
  <div id="house">—</div>
  <ul id="reasons"></ul>
  <div class="bar"><i id="bar"></i></div>
  <div id="lat">等待第一次会话…</div>
  <p style="color:#666;font-size:12px">AI 合成语音 · 非医疗器械 · 不构成任何评估</p>
</main>
<script>
const NAMES={courage:"赤翎",ambition:"玄渊",wisdom:"星枢",loyalty:"穗垣"};
async function tick(){
  try{
    const s=await (await fetch("/stats")).json();
    const last=s.last||{}; const v=last.latency||{};
    if(last.house){document.getElementById("house").textContent=NAMES[last.house]||last.house;}
    if(last.reasons){document.getElementById("reasons").innerHTML=
      last.reasons.map(r=>`<li>「${r}」</li>`).join("");}
    document.getElementById("lat").textContent=
      `TTFC ${v.host_ms||"-"} ms（上位机段） · ${last.text||""}`;
    document.getElementById("bar").style.width=Math.min(100,100*(v.host_ms||0)/1240)+"%";
  }catch(e){}
}
setInterval(tick,700); tick();
</script></html>"""
