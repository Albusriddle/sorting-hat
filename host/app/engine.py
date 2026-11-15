from __future__ import annotations
import asyncio
import time
from . import judge, protocol
from .config import settings
from .providers import Provider


def ms() -> int:
    return int(time.monotonic() * 1000)


class SessionEngine:
    """One session: ASR -> LLM -> judge -> TTS. Every step has a soft timeout + fallback."""

    def __init__(self, asr, llm, tts, state):
        self.asr: Provider = asr
        self.llm: Provider = llm
        self.tts = tts
        self.state = state

    async def run(self, emit, text_hint: str = "", t0: int | None = None,
                  t1: int | None = None) -> dict:
        t0 = t0 or ms()
        t1 = t1 or t0
        degrade: list[str] = []

        # --- ASR -------------------------------------------------------
        t_asr = ms()
        try:
            text = await asyncio.wait_for(self.asr.final(text_hint),
                                          timeout=settings.asr_timeout_ms / 1000)
        except asyncio.TimeoutError:
            degrade.append("asr_timeout")
            text = text_hint or "我没听清。"
        t2 = ms()

        # --- LLM -------------------------------------------------------
        t_llm = ms()
        try:
            payload = await asyncio.wait_for(self.llm.complete(text),
                                             timeout=settings.llm_timeout_ms / 1000)
        except asyncio.TimeoutError:
            degrade.append("llm_timeout")
            payload = {"evidence": [{"quote": text[:10], "trait": "courage", "why": "兜底"}],
                       "scores": {"courage": 5, "ambition": 4, "wisdom": 4, "loyalty": 4},
                       "line": "唔……让我看看。你身上有股不服气的劲儿。"}
        t3 = ms()

        verdict = judge.decide(text, payload, list(self.state.recent_houses),
                               penalty=settings.recent3_penalty,
                               max_share=settings.max_share)
        if verdict["degraded"]:
            degrade.append("quote_fail")

        # --- TTS -------------------------------------------------------
        tts_text = verdict["line"]
        await emit(protocol.tts("start", 1, tts_text))
        t_tts = ms()
        try:
            frames = await asyncio.wait_for(self.tts.synth_async(tts_text),
                                            timeout=settings.tts_timeout_ms / 1000)
        except asyncio.TimeoutError:
            degrade.append("tts_timeout")
            frames = self.tts.synth("唔……") if hasattr(self.tts, "synth") else []
        for i, f in enumerate(frames):
            await emit(protocol.audio_frame(i, f))
        t4 = ms()
        await emit(protocol.tts("stop", 1))

        latency = {
            "t0": t0, "t1": t1, "t2": t2, "t3": t3, "t4": t4,
            "asr_ms": t2 - t1, "llm_ms": t3 - t2, "tts_ms": t4 - t3,
            "host_ms": t4 - t1, "degrade": degrade,
        }
        await emit(protocol.result(verdict["house"], verdict["reasons"],
                                   verdict["line"], latency))
        self.state.recent_houses.append(verdict["house"])
        self.state.sessions += 1
        self.state.last_stats = {"house": verdict["house"], "latency": latency,
                                 "text": text, "quote_ok": verdict["quote_ok"]}
        return {"text": text, "verdict": verdict, "latency": latency, "degrade": degrade}
