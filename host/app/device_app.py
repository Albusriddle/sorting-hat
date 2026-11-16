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
    return bool(tok) and bool(settings.device_token) and tok == settings.device_token


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
        await emit(protocol.tts("start", 1, text))
        try:
            frames = await asyncio.wait_for(TTS.synth_async(text),
                                            timeout=settings.tts_timeout_ms / 1000)
        except Exception:
            frames = TTS.synth("唔……") if hasattr(TTS, "synth") else []
        for i, f in enumerate(frames):
            await emit(protocol.audio_frame(i, f))
            await asyncio.sleep(settings.tts_pace_ms / 1000)   # 默认 60 ms/帧，避免 stop 立刻掐断
        await emit(protocol.tts("stop", 1))

    task: asyncio.Task | None = None
    silence_task: asyncio.Task | None = None
    watchdog: asyncio.Task | None = None
    pending: dict[str, dict] = {}
    timers: dict[str, asyncio.Task] = {}
    last_text = ""
    last_speech = 0.0
    rescued = False

    def flush(session_id: str, dev_ts: dict | None = None) -> None:
        row = pending.pop(session_id, None)
        timer = timers.pop(session_id, None)
        if timer and not timer.done():
            timer.cancel()
        if not row:
            return
        if dev_ts:
            t0 = dev_ts.get("t0")
            t5a = dev_ts.get("t5a", t0)
            t5b = dev_ts.get("t5b", t0)
            if t0 and t5b:
                row["ttfc_ms"] = int(t5b) - int(t0)
                row["ttfv_ms"] = int(t5a or t0) - int(t0)
            row["dev_ts"] = dev_ts
        record(row)

    async def flush_later(session_id: str, delay: float = 2.0) -> None:
        await asyncio.sleep(delay)
        flush(session_id)

    def _collect(fut) -> None:
        try:
            out = fut.result()
        except Exception:
            return
        # watchdog 只管"这一轮听", 结果出来就停
        if watchdog and not watchdog.done():
            watchdog.cancel()
        if not out or not out.get("verdict"):
            return
        row = {"sid": sid, "text": out.get("text"),
               "house": out["verdict"]["house"],
               "reasons": out["verdict"]["reasons"],
               "scores": out["verdict"]["scores"],
               "latency": out.get("latency"),
               "degrade": out.get("degrade", []),
               "audio": STATE.session_audio.get(sid, {})}
        pending[sid] = row
        timers[sid] = asyncio.create_task(flush_later(sid))

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

    async def cancel(*tasks):
        for t in tasks:
            if t and not t.done():
                t.cancel()

    def start_silence() -> asyncio.Task:
        nonlocal last_speech, rescued
        last_speech = time.monotonic()
        rescued = False
        return asyncio.create_task(silence_monitor())

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
                    await cancel(silence_task, watchdog)
                    silence_task = start_silence()
                    watchdog = asyncio.create_task(session_watchdog())

                elif t == "vad" and data.get("ev") == "speech_start":
                    last_speech = time.monotonic()

                elif t == "vad" and data.get("ev") == "speech_end":
                    last_speech = time.monotonic()
                    if task and not task.done():
                        continue                      # 同一轮只跑一次
                    pcm = audio.pcm()
                    stats = {**audio.stats(), "rms": pcm_rms(pcm)}
                    STATE.set_audio(sid, stats)
                    await cancel(silence_task, watchdog)   # 计时按"轮"，本轮到此结束
                    t0 = ms()
                    has_text = bool((last_text or "").strip())
                    if has_text:
                        pass                                # 有文字就用文字，完全不看音频
                    elif settings.asr_provider == "mock":
                        # mock ASR 不看 pcm，不能凭"底噪"凭空判院
                        await send_tts_line("唔……我没听清，再说一次？")
                        continue
                    elif not pcm or stats["rms"] < settings.min_audio_rms:
                        await send_tts_line("唔……我没听清，再说一次？")
                        continue
                    task = asyncio.create_task(ENGINE.run(emit, last_text, t0=t0, t1=ms(),
                                                          pcm=pcm, sid=sid))
                    task.add_done_callback(_collect)

                elif t == "abort":
                    await cancel(task, silence_task, watchdog)
                    audio.reset()
                    flush(sid)
                    await ws.send_json(protocol.bye("doff"))

                elif t == "ping":
                    await ws.send_json({"type": "pong"})

                elif t == "bye":
                    await cancel(silence_task, watchdog)
                    flush(sid, data.get("dev_ts"))
                    # done = 设备把 dev_ts 交上来，但连接继续复用；其余原因才收尾
                    if data.get("reason") != "done":
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
        for session_id in list(pending):
            flush(session_id)
        STATE.drop_sid(sid)
        try:
            await ws.close()
        except Exception:
            pass
