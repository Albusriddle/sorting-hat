
from __future__ import annotations
import asyncio
import time

from . import judge, protocol
from .config import settings
from .persona import bridge_line, pick_announcement
from .providers import Provider


def ms() -> int:
    return int(time.monotonic() * 1000)


class SessionEngine:
    """One session: text (or ASR) -> LLM -> judge -> TTS bridge -> result."""

    def __init__(self, asr, llm, tts, state):
        self.asr: Provider = asr
        self.llm: Provider = llm
        self.tts = tts
        self.state = state

    async def _speak(self, emit, text: str, degrade: list[str]) -> None:
        await emit(protocol.tts("start", 1, text))
        try:
            frames = await asyncio.wait_for(self.tts.synth_async(text),
                                            timeout=settings.tts_timeout_ms / 1000)
        except asyncio.TimeoutError:
            degrade.append("tts_timeout")
            frames = self.tts.synth("唔……") if hasattr(self.tts, "synth") else []
        except Exception:
            degrade.append("tts_unavailable")
            frames = []
        for i, f in enumerate(frames):
            await emit(protocol.audio_frame(i, f))
        await emit(protocol.tts("stop", 1))

    async def run(self, emit, text_hint: str = "", t0: int | None = None,
                  t1: int | None = None, pcm: bytes | None = None,
                  sid: str | None = None) -> dict:
        t0 = t0 or ms()
        t1 = t1 or ms()
        degrade: list[str] = []

        # ---- text first: 设备发来的词条文本优先，没有才走 ASR ----
        text = (text_hint or "").strip()
        if not text:
            try:
                text = (await asyncio.wait_for(self.asr.final("", pcm=pcm),
                                               timeout=settings.asr_timeout_ms / 1000) or "").strip()
            except asyncio.TimeoutError:
                degrade.append("asr_timeout")
            except Exception:
                degrade.append("asr_unavailable")
        t2 = ms()
        if not text:
            await self._speak(emit, "唔……我没听清，再说一次？", degrade)
            return {"aborted": "asr", "degrade": degrade, "sid": sid, "latency": {"t0": t0, "t1": t1, "t2": t2}}

        # ---- LLM ----
        try:
            payload = await asyncio.wait_for(self.llm.complete(text),
                                             timeout=settings.llm_timeout_ms / 1000)
        except asyncio.TimeoutError:
            degrade.append("llm_timeout")
            payload = {"evidence": [{"quote": text[:10], "trait": "courage", "why": "兜底"}],
                       "scores": {"courage": 5, "ambition": 4, "wisdom": 4, "loyalty": 4},
                       "line": "唔……让我看看。"}
        except Exception:
            degrade.append("llm_unavailable")
            payload = {"evidence": [{"quote": text[:10], "trait": "courage", "why": "兜底"}],
                       "scores": {"courage": 5, "ambition": 4, "wisdom": 4, "loyalty": 4},
                       "line": "唔……让我看看。"}
        t3 = ms()

        if payload.get("refuse"):
            await self._speak(emit, "这顶帽子不管这个。", degrade)
            return {"aborted": "refuse", "degrade": degrade, "sid": sid,
                    "latency": {"t0": t0, "t1": t1, "t2": t2, "t3": t3}}

        verdict = judge.decide(text, payload, list(self.state.recent_for(sid or "")),
                               penalty=settings.recent3_penalty,
                               max_share=settings.max_share,
                               min_history=settings.min_history_for_balance)
        if verdict.get("insufficient"):
            await self._speak(emit, "唔……再说一句？", degrade)
            return {"aborted": "insufficient", "degrade": degrade, "sid": sid,
                    "latency": {"t0": t0, "t1": t1, "t2": t2, "t3": t3}}

        # ---- TTS 只念与学院无关的桥接句，避免"念 A 宣布 B" ----
        bridge = bridge_line(self.state.sessions)
        await self._speak(emit, bridge, degrade)
        t4 = ms()

        house = verdict["house"]
        announce_text, variant = pick_announcement(house, self.state.sessions)
        latency = {
            "t0": t0, "t1": t1, "t2": t2, "t3": t3, "t4": t4,
            "asr_ms": t2 - t1, "llm_ms": t3 - t2, "tts_ms": t4 - t3,
            "host_ms": t4 - t1, "degrade": degrade,
        }
        await emit(protocol.result(house, verdict["reasons"], announce_text, latency,
                                   scores={k: round(v, 1) for k, v in verdict["scores"].items()},
                                   announce={"variant": variant,
                                             "file": f"{house}-{variant + 1}.opus"}))
        self.state.recent_for(sid or "").append(house)
        self.state.sessions += 1
        self.state.set_stats(sid or "", {"house": house, "latency": latency, "text": text,
                                         "reasons": verdict["reasons"], "scores": verdict["scores"],
                                         "quote_ok": verdict["quote_ok"], "sid": sid})
        return {"text": text, "verdict": verdict, "latency": latency,
                "degrade": degrade, "sid": sid}
