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
    # 一轮一行：键是 (sid, 轮次)，不是 sid —— 连接复用后同一 sid 会跑很多场
    pending: dict[str, dict] = {}
    timers: dict[str, asyncio.Task] = {}
    recorded: set[str] = set()
    last_text = ""
    last_speech = 0.0
    rescued = False
    rescued_round = False
    round_start = 0.0
    seq = 0
    key = f"{sid}#0"
    heard = asyncio.Event()

    def new_round() -> str:
        nonlocal seq, key
        seq += 1
        key = f"{sid}#{seq}"
        return key

    def record_aborted(reason: str, text: str = "") -> None:
        if key in recorded:
            return
        recorded.add(key)
        record({"sid": sid, "round": seq, "outcome": "aborted", "reason": reason,
                "text": text or last_text, "degrade": [reason],
                "rescue": rescued_round,
                "audio": STATE.session_audio.get(sid, {})})

    def flush(row_key: str, dev_ts: dict | None = None) -> None:
        row = pending.pop(row_key, None)
        timer = timers.pop(row_key, None)
        if timer and not timer.done():
            timer.cancel()
        if not row:
            return
        recorded.add(row_key)
        if dev_ts:
            t0 = dev_ts.get("t0")
            t5a = dev_ts.get("t5a", t0)
            t5b = dev_ts.get("t5b", t0)
            if t0 and t5b:
                d = int(t5b) - int(t0)
                dv = int(t5a or t0) - int(t0)
                # 救场句的 0x02 帧会先抢 t5b：这一轮的 TTFC 不能当作"宣布出声"
                if rescued_round:
                    row["ttfc_suspect"] = True
                # 设备打点可能早于 t0（t5b < t0），不要让负数/回绕进库
                if 0 <= d <= settings.session_max_ms:
                    row["ttfc_ms"] = d
                else:
                    row["ttfc_ms"] = None
                    row["clock_skew"] = d
                row["ttfv_ms"] = dv if 0 <= dv <= settings.session_max_ms else None
            row["dev_ts"] = dev_ts
        record(row)

    async def flush_later(row_key: str, delay: float = 10.0) -> None:
        await asyncio.sleep(delay)
        flush(row_key)

    def _collect(fut, row_key: str) -> None:
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
        row = {"sid": sid, "round": seq, "text": out.get("text"),
               "house": out["verdict"]["house"],
               "reasons": out["verdict"]["reasons"],
               "scores": out["verdict"]["scores"],
               "latency": out.get("latency"),
               "degrade": out.get("degrade", []),
               "rescue": rescued_round,
               "audio": STATE.session_audio.get(sid, {})}
        pending[row_key] = row
        timers[row_key] = asyncio.create_task(flush_later(row_key))

    async def silence_monitor():
        nonlocal last_speech, rescued, rescued_round
        while not heard.is_set():
            await asyncio.sleep(0.2)
            if heard.is_set():
                return
            if not last_speech:
                continue
            idle = time.monotonic() - last_speech
            elapsed = time.monotonic() - round_start
            if idle >= settings.silence_ms / 1000 and not rescued:
                rescued = True
                rescued_round = True
                # shield：即使此时收到 speech_start，也让这一句完整发完
                await asyncio.shield(send_tts_line("唔……你在想什么呢？"))
                if heard.is_set():
                    return
                last_speech = time.monotonic()   # 重锚：救场后重新给一整段，而不是只剩 8 s
                idle = 0.0
            # bye 双条件：空闲够久，或整轮触到硬上限（必须早于固件 30 s 超时）
            if idle >= settings.silence_bye_ms / 1000 or \
               elapsed >= settings.silence_hard_cap_ms / 1000:
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
        nonlocal last_speech, rescued, rescued_round, round_start
        last_speech = time.monotonic()
        round_start = time.monotonic()
        rescued = False
        rescued_round = False
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
                    new_round()                    # 一轮一行，键带轮次
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
                    row_key = key
                    task = asyncio.create_task(ENGINE.run(emit, last_text, t0=t0, t1=ms(),
                                                          pcm=pcm, sid=sid))
                    task.add_done_callback(lambda f, k=row_key: _collect(f, k))

                elif t == "abort":
                    await cancel(task, silence_task, watchdog)
                    audio.reset()
                    flush(key)
                    record_aborted("doff", last_text)
                    await ws.send_json(protocol.bye("doff"))

                elif t == "ping":
                    await ws.send_json({"type": "pong"})

                elif t == "bye":
                    await cancel(silence_task, watchdog)
                    flush(key, data.get("dev_ts"))
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
        for row_key in list(pending):
            flush(row_key)
        STATE.drop_sid(sid)
        try:
            await ws.close()
        except Exception:
            pass
