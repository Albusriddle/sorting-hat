from __future__ import annotations
import json
from pathlib import Path
from fastapi import FastAPI, Header, HTTPException, Body
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse

from . import judge, protocol
from .config import settings
from .metrics import tail, record
from .persona import load_houses, load_lines, load_prompt
from .preheat import run_preheat
from .providers import MockLLM
from .state import STATE

admin_app = FastAPI(title="sortinghat-admin")
ROOT = Path(__file__).resolve().parent.parent


def _auth(token: str | None):
    if token != settings.admin_token:
        raise HTTPException(status_code=401, detail="admin token required")


@admin_app.get("/healthz")
async def healthz():
    return {"ok": True}


@admin_app.get("/readyz")
async def readyz():
    last = ROOT / settings.data_dir / "preheat.json"
    ok = last.exists()
    return JSONResponse({"ok": ok, "preheat": json.loads(last.read_text()) if ok else None},
                        status_code=200 if ok else 503)


@admin_app.post("/v1/preheat")
async def preheat(x_admin_token: str | None = Header(default=None)):
    _auth(x_admin_token)
    res = await run_preheat()
    return res


@admin_app.post("/v1/replay")
async def replay(payload: dict = Body(default={}), x_admin_token: str | None = Header(default=None)):
    _auth(x_admin_token)
    text = payload.get("text") or "我最想要的是被认可，但我又不想说出来。"
    llm = MockLLM()
    p = await llm.complete(text)
    v = judge.decide(text, p, payload.get("recent", []),
                     penalty=settings.recent3_penalty, max_share=settings.max_share)
    return {"house": v["house"], "reasons": v["reasons"], "quote_ok": v["quote_ok"]}


@admin_app.get("/v1/sessions")
async def sessions(n: int = 20, x_admin_token: str | None = Header(default=None)):
    _auth(x_admin_token)
    return {"rows": tail(n)}


@admin_app.get("/stats")
async def stats():
    return STATE.snapshot()


@admin_app.get("/v1/metrics", response_class=PlainTextResponse)
async def metrics():
    s = STATE.snapshot()
    last = s.get("last") or {}
    lat = last.get("latency") or {}
    lines = [
        f"# HELP sortinghat_sessions_total sessions served",
        f"sortinghat_sessions_total {s['sessions']}",
        f"# HELP sortinghat_errors_total protocol errors",
        f"sortinghat_errors_total {s['errors']}",
        f"# HELP sortinghat_ttfc_ms last session TTFC (host side)",
        f"sortinghat_ttfc_ms {lat.get('host_ms', -1)}",
    ]
    return "\n".join(lines) + "\n"


@admin_app.post("/v1/config")
async def config(payload: dict = Body(default={}), x_admin_token: str | None = Header(default=None)):
    _auth(x_admin_token)
    STATE.config.update(payload)
    return {"ok": True, "config": STATE.config}


@admin_app.post("/v1/halt")
async def halt(payload: dict = Body(default={}), x_admin_token: str | None = Header(default=None)):
    _auth(x_admin_token)
    mode = payload.get("mode", "halt_new")
    if mode not in ("none", "halt_new", "stop_all"):
        raise HTTPException(status_code=400, detail="bad mode")
    STATE.halt = mode
    return {"ok": True, "halt": mode}


@admin_app.get("/", response_class=HTMLResponse)
async def console():
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
    const ul=document.getElementById("reasons");
    if(last.latency){ul.innerHTML=(last.reasons||[]).map(r=>`<li>「${r}」</li>`).join("");}
    document.getElementById("lat").textContent=
      `TTFC ${v.host_ms||"-"} ms（上位机段） · ${last.text||""}`;
    const w=Math.min(100,100*(v.host_ms||0)/1240);
    document.getElementById("bar").style.width=w+"%";
  }catch(e){}
}
setInterval(tick,700); tick();
</script></html>"""
