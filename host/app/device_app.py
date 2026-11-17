from __future__ import annotations
import array
import asyncio
import json
import time

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from . import protocol
from .audio import SessionAudio
from .config import settings, validate_settings
from .engine import SessionEngine, ms
from .metrics import record
from .providers import build_providers
from .state import STATE

validate_settings()

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

    tts_lock = asyncio.Lock()

    async def send_tts_line(text: str) -> None:
        async with tts_lock:
            await _send_tts_line(text)

    async def _send_tts_line(text: str) -> None:
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
    recorded: set[str] = set()
    last_text = ""
    last_speech = 0.0
    rescued = False
    heard = asyncio.Event()

    def record_aborted(reason: str, text: str = "") -> None:
        if sid in recorded:
            return
        recorded.add(sid)
        record({"sid": sid, "outcome": "aborted", "reason": reason,
                "text": text or last_text, "degrade": [reason],
                "audio": STATE.session_audio.get(sid, {})})

    def flush(session_id: str, dev_ts: dict | None = None) -> None:
        row = pending.pop(session_id, None)
        timer = timers.pop(session_id, None)
        if timer and not timer.done():
            timer.cancel()
        if not row:
            return
        recorded.add(session_id)
        if dev_ts:
            t0 = dev_ts.get("t0")
            t5a = dev_ts.get("t5a", t0)
            t5b = dev_ts.get("t5b", t0)
            if t0 and t5b:
                d = int(t5b) - int(t0)
                dv = int(t5a or t0) - int(t0)
                # 设备打点可能早于 t0（t5b < t0），不要让负数/回绕进库
                if 0 <= d <= settings.session_max_ms:
                    row["ttfc_ms"] = d
                else:
                    row["ttfc_ms"] = None
                    row["clock_skew"] = d
                row["ttfv_ms"] = dv if 0 <= dv <= settings.session_max_ms else None
            row["dev_ts"] = dev_ts
        record(row)

    async def flush_later(session_id: str, delay: float = 10.0) -> None:
        await asyncio.sleep(delay)
        flush(session_id)

    def _collect(fut) -> None:
        try:
            out = fut.result()
        except asyncio.CancelledError:
            return
        except Exception:
            return
        # watchdog 只管"这一轮听", 结果出来就停
        if watchdog and not watchdog.done():
            watchdog.cancel()
        if not out:
            return
        if out.get("aborted"):
            record_aborted(str(out.get("aborted")), out.get("text", ""))
            return
        if not out.get("verdict"):
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
        while not heard.is_set():
            await asyncio.sleep(0.2)
            if heard.is_set():
                return
            if not last_speech:
                continue
            idle = time.monotonic() - last_speech
            if idle >= settings.silence_ms / 1000 and not rescued:
                rescued = True
                # shield：即使此时收到 speech_start，也让这一句完整发完
                await asyncio.shield(send_tts_line("唔……你在想什么呢？"))
                if heard.is_set():
                    return
            if idle >= settings.silence_bye_ms / 1000:
                await ws.send_json(protocol.bye("silence"))
                try:
                    await ws.close()
                except Exception:
                    pass
                return

    async def session_watchdog():
        await asyncio.sleep(settings.session_max_ms / 1000)
        await cancel(silence_task, task)        # 先停计时/引擎，避免关闭后还写 socket
        record_aborted("timeout")
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
        heard.clear()
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
                    recorded.discard(sid)          # 新一轮允许再记一行
                    audio.reset()
                    async with tts_lock:            # 等上一句发完，避免旧救场句串到新会话
                        await cancel(silence_task, watchdog)
                    silence_task = start_silence()
                    watchdog = asyncio.create_task(session_watchdog())

                elif t == "vad" and data.get("ev") == "speech_start":
                    last_speech = time.monotonic()
                    heard.set()                    # "听到了" → 停表（不打断正在发的句子）

                elif t == "vad" and data.get("ev") == "speech_end":
                    last_speech = time.monotonic()
                    if task and not task.done():
                        continue                      # 同一轮只跑一次
                    pcm = audio.pcm()
                    stats = {**audio.stats(), "rms": pcm_rms(pcm)}
                    STATE.set_audio(sid, stats)
                    heard.set()                    # 本轮计时结束；watchdog 留到结果完成
                    t0 = ms()
                    has_text = bool((last_text or "").strip())
                    if has_text:
                        pass                                # 有文字就用文字，完全不看音频
                    elif settings.asr_provider == "mock":
                        # mock ASR 不看 pcm，不能凭"底噪"凭空判院
                        record_aborted("no_text_mock", last_text)
                        await send_tts_line("唔……我没听清，再说一次？")
                        continue
                    elif not pcm or stats["rms"] < settings.min_audio_rms:
                        record_aborted("silent_audio", last_text)
                        await send_tts_line("唔……我没听清，再说一次？")
                        continue
                    task = asyncio.create_task(ENGINE.run(emit, last_text, t0=t0, t1=ms(),
                                                          pcm=pcm, sid=sid))
                    task.add_done_callback(_collect)

                elif t == "abort":
                    await cancel(task, silence_task, watchdog)
                    audio.reset()
                    flush(sid)
                    record_aborted("doff", last_text)
                    await ws.send_json(protocol.bye("doff"))

                elif t == "ping":
                    await ws.send_json({"type": "pong"})

                elif t == "bye":
                    await cancel(silence_task, watchdog)
                    flush(sid, data.get("dev_ts"))
                    # 连接复用：任何 reason 都只结算本轮，不主动断开；
                    # 真正断开只由 WebSocket 关闭决定（避免 2 秒重连空档）。
                    continue

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
