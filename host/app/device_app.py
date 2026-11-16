
from __future__ import annotations
import array
import asyncio
import json
import time

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from . import protocol
from .audio import SessionAudio
from .config import settings
from .engine import SessionEngine, ms
from .metrics import record
from .providers import build_providers
from .state import STATE

device_app = FastAPI(title="sortinghat-device")

ASR, LLM, TTS = build_providers(settings)
ENGINE = SessionEngine(ASR, LLM, TTS, STATE)


def _token_of(ws: WebSocket) -> str:
    auth = ws.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return ws.query_params.get("token", "").strip()


def _authorized(ws: WebSocket) -> bool:
    tok = _token_of(ws)
    return bool(tok) and tok == settings.device_token


def pcm_rms(pcm: bytes) -> int:
    if not pcm:
        return 0
    a = array.array("h")
    a.frombytes(pcm[: len(pcm) // 2 * 2])
    if not a:
        return 0
    return int((sum(int(x) * int(x) for x in a) / len(a)) ** 0.5)


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
    audio = SessionAudio()
    await ws.send_json(protocol.ready(sid))

    async def emit(m):
        if isinstance(m, (bytes, bytearray)):
            await ws.send_bytes(bytes(m))
        else:
            await ws.send_json(m)

    async def send_tts_line(text: str) -> None:
        """Short host-side line: tts start -> frames -> stop (device may speak via I2C)."""
        await emit(protocol.tts("start", 1, text))
        try:
            frames = await asyncio.wait_for(TTS.synth_async(text),
                                            timeout=settings.tts_timeout_ms / 1000)
        except Exception:
            frames = TTS.synth("唔……") if hasattr(TTS, "synth") else []
        for i, f in enumerate(frames):
            await emit(protocol.audio_frame(i, f))
        await emit(protocol.tts("stop", 1))

    task: asyncio.Task | None = None
    silence_task: asyncio.Task | None = None
    watchdog: asyncio.Task | None = None
    last_text = ""
    last_speech = 0.0
    rescued = False
    row: dict = {}
    recorded = False

    def finish_row(dev_ts: dict | None = None) -> None:
        nonlocal recorded
        if recorded or not row:
            return
        recorded = True
        if dev_ts:
            t0 = dev_ts.get("t0")
            t5b = dev_ts.get("t5b")
            if t0 and t5b:
                row["ttfc_ms"] = int(t5b) - int(t0)
                row["ttfv_ms"] = int(dev_ts.get("t5a", t5b)) - int(t0)
            row["dev_ts"] = dev_ts
        record(row)

    async def silence_monitor():
        nonlocal rescued
        while True:
            await asyncio.sleep(0.5)
            if not last_speech:
                continue
            idle = time.monotonic() - last_speech
            if idle >= settings.silence_ms / 1000 and not rescued:
                rescued = True
                await send_tts_line("唔……你在想什么呢？")
            if idle >= settings.silence_bye_ms / 1000:
                await ws.send_json(protocol.bye("silence"))
                try:
                    await ws.close()
                except Exception:
                    pass
                return

    async def session_watchdog():
        await asyncio.sleep(settings.session_max_ms / 1000)
        try:
            await ws.send_json(protocol.bye("timeout"))
            await ws.close()
        except Exception:
            pass

    def _collect(fut):
        nonlocal row
        try:
            out = fut.result()
        except Exception:
            return
        if out and out.get("verdict"):
            row = {"sid": sid, "text": out.get("text"),
                   "house": out["verdict"]["house"],
                   "reasons": out["verdict"]["reasons"],
                   "scores": out["verdict"]["scores"],
                   "latency": out.get("latency"),
                   "degrade": out.get("degrade", []),
                   "audio": STATE.last_audio}

    async def cancel(*tasks):
        for t in tasks:
            if t and not t.done():
                t.cancel()

    try:
        while True:
            msg = await ws.receive()
            if msg.get("type") == "websocket.disconnect":
                break
            if msg.get("text") is not None:
                data = json.loads(msg["text"])
                t = data.get("type")

                if t == "text":
                    last_text = str(data.get("text", ""))[: settings.text_max_chars]

                elif t == "listen" and data.get("state") == "start":
                    if STATE.halt != "none":
                        await ws.send_json(protocol.error("rate_limited", "halt", False))
                        continue
                    last_text = ""
                    audio.reset()
                    rescued = False
                    last_speech = 0.0
                    await cancel(silence_task, watchdog)
                    silence_task = asyncio.create_task(silence_monitor())
                    watchdog = asyncio.create_task(session_watchdog())

                elif t == "vad" and data.get("ev") == "speech_start":
                    last_speech = time.monotonic()

                elif t == "vad" and data.get("ev") == "speech_end":
                    last_speech = time.monotonic()
                    if task and not task.done():
                        continue                      # 同一会话只跑一次
                    pcm = audio.pcm()
                    STATE.last_audio = {**audio.stats(), "rms": pcm_rms(pcm)}
                    await cancel(silence_task)
                    t0 = ms()
                    # 静音闸：全零/过低能量不判院（长度闸无效，设备必发固定帧数）
                    if not pcm or pcm_rms(pcm) < settings.min_audio_rms:
                        await send_tts_line("唔……我没听清，再说一次？")
                        continue
                    task = asyncio.create_task(ENGINE.run(emit, last_text, t0=t0, t1=ms(),
                                                          pcm=pcm, sid=sid))
                    task.add_done_callback(lambda fut: _collect(fut))

                elif t == "abort":
                    await cancel(task, silence_task, watchdog)
                    audio.reset()
                    await ws.send_json(protocol.bye("doff"))

                elif t == "ping":
                    await ws.send_json({"type": "pong"})

                elif t == "bye":
                    finish_row(data.get("dev_ts"))
                    break

            elif msg.get("bytes") is not None:
                b = msg["bytes"]
                if b and b[0] == 0x01:
                    audio.push_opus(b[5:])
                elif b and b[0] == 0x04:
                    audio.push_pcm(b[5:])
                else:
                    await ws.send_json(protocol.error("bad_frame", "dropped", False))
                    STATE.errors += 1

    except WebSocketDisconnect:
        pass
    except Exception as exc:
        STATE.errors += 1
        try:
            await ws.send_json(protocol.error("upstream_5xx", str(exc)[:80], False))
        except Exception:
            pass
    finally:
        await cancel(task, silence_task, watchdog)
        finish_row()
        STATE.drop_sid(sid)
        try:
            await ws.close()
        except Exception:
            pass
