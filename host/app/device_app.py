from __future__ import annotations
import asyncio
import json
from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from . import protocol
from .config import settings
from .engine import SessionEngine, ms
from .metrics import record
from .providers import MockASR, MockLLM, MockTTS
from .state import STATE

device_app = FastAPI(title="sortinghat-device")

ASR = MockASR()
LLM = MockLLM()
TTS = MockTTS()
ENGINE = SessionEngine(ASR, LLM, TTS, STATE)


def _authorized(ws: WebSocket) -> bool:
    auth = ws.headers.get("authorization", "")
    return auth.startswith("Bearer ") or ws.query_params.get("token") is not None


@device_app.get("/healthz")
async def healthz():
    return {"ok": True}


@device_app.websocket("/v1/voice")
async def voice(ws: WebSocket):
    if not _authorized(ws):
        await ws.close(code=4401)
        return
    await ws.accept(subprotocol=protocol.PROTOCOL)
    sid = protocol.new_sid()
    await ws.send_json(protocol.ready(sid))

    async def emit(m):
        if isinstance(m, (bytes, bytearray)):
            await ws.send_bytes(bytes(m))
        else:
            await ws.send_json(m)

    task: asyncio.Task | None = None
    last_text = ""

    try:
        while True:
            msg = await ws.receive()
            if msg.get("type") == "websocket.disconnect":
                break
            if msg.get("text") is not None:
                data = json.loads(msg["text"])
                t = data.get("type")
                if t == "listen" and data.get("state") == "start":
                    last_text = ""
                elif t == "vad" and data.get("ev") == "speech_end":
                    if STATE.halt == "stop_all":
                        await ws.send_json(protocol.error("rate_limited", "halt", False))
                        continue
                    t1 = ms()
                    task = asyncio.create_task(
                        ENGINE.run(emit, last_text, t0=t1, t1=t1))
                elif t == "abort":
                    if task and not task.done():
                        task.cancel()
                    await ws.send_json(protocol.bye("doff"))
                elif t == "ping":
                    await ws.send_json({"type": "pong"})
                elif t == "bye":
                    break
            elif msg.get("bytes") is not None:
                b = msg["bytes"]
                # 0x01 | seq u32 | opus. We do not decode in the MVP.
                if not b or b[0] != 0x01:
                    await ws.send_json(protocol.error("bad_frame", "dropped", False))
                    STATE.errors += 1
    except WebSocketDisconnect:
        pass
    except Exception as exc:  # never kill the loop on a bad frame
        STATE.errors += 1
        try:
            await ws.send_json(protocol.error("upstream_5xx", str(exc)[:80], False))
        except Exception:
            pass
    finally:
        if task and not task.done():
            task.cancel()
        try:
            await ws.close()
        except Exception:
            pass
