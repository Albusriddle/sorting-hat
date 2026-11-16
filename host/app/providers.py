
from __future__ import annotations
import asyncio
import math
import re
import struct
from dataclasses import dataclass, field


@dataclass
class Event:
    kind: str                       # partial | final | audio | done | error
    text: str = ""
    pcm: bytes = b""
    code: str = ""
    retryable: bool = False


class Provider:
    name = "base"

    async def health(self) -> bool:
        return True

    async def warmup(self) -> None:
        return None


class MockASR(Provider):
    """Deterministic ASR: returns whatever text the caller supplied (demo)."""
    name = "mock-asr"

    def __init__(self, canned: str = ""):
        self.canned = canned

    async def final(self, text_hint: str = "", pcm: bytes | None = None) -> str:
        await asyncio.sleep(0.02)
        return text_hint or self.canned or "我最想要的是被认可，但我又不想说出来。"


class MockLLM(Provider):
    """Deterministic scorer used for the demo. Never invents a house."""
    name = "mock-llm"

    KEYS = {
        "courage":  ("怕输", "退缩", "不敢", "硬着头皮", "豁出去"),
        "ambition": ("想要", "目标", "第一", "认可", "拿到手", "升"),
        "wisdom":   ("拆开", "想清楚", "琢磨", "研究", "为什么", "书"),
        "loyalty":  ("身边", "在乎", "需要我", "缺席", "朋友", "家人", "护着"),
    }
    LINES = {
        "courage": "有意思。你不怕撞墙，那就去撞出个名堂吧。",
        "ambition": "你要的东西不小。那就去拿，别只是看着。",
        "wisdom": "你脑子转得比嘴快。去那里，慢慢想清楚。",
        "loyalty": "你护着的人不少。去那里，继续护着。",
    }

    @staticmethod
    def _clauses(text: str) -> list[str]:
        parts = [c.strip() for c in re.split(r"[，。！？、,.!?；;]", text) if c.strip()]
        return parts or [text]

    async def complete(self, text: str) -> dict:
        await asyncio.sleep(0.03)
        clauses = self._clauses(text)
        scores, evidence, used = {}, [], set()
        for dim, keys in self.KEYS.items():
            hits = [k for k in keys if k in text]
            scores[dim] = float(3 + 2 * len(hits))
            if not hits:
                continue
            quote = next((c for c in clauses if hits[0] in c and c not in used),
                         next((c for c in clauses if c not in used), clauses[0]))
            used.add(quote)
            evidence.append({"quote": quote[:14], "trait": dim, "why": f"出现「{hits[0]}」"})
            if len(evidence) == 3:
                break
        if not evidence:
            # 不伪造证据：四维全不命中就明确返回 insufficient，让引擎去追问
            return {"evidence": [], "scores": scores, "line": "", "insufficient": True}
        best = max(scores, key=scores.get)
        return {"evidence": evidence, "scores": scores, "line": self.LINES[best]}


class MockTTS(Provider):
    """Emits deterministic 60 ms PCM (16 kHz mono, 220 Hz) frames."""
    name = "mock-tts"

    def __init__(self, sample_rate: int = 16000, frame_ms: int = 60, freq: float = 220.0):
        self.sample_rate = sample_rate
        self.frame_ms = frame_ms
        self.freq = freq

    async def synth_async(self, text: str, max_ms: int = 1200) -> list[bytes]:
        return self.synth(text, max_ms)

    def synth(self, text: str, max_ms: int = 1200) -> list[bytes]:
        total = min(max_ms, 240 + 90 * len(text))
        n_per_frame = int(self.sample_rate * self.frame_ms / 1000)
        frames, sent = [], 0
        i = 0
        while sent < total:
            buf = bytearray()
            for _ in range(n_per_frame):
                v = int(3000 * math.sin(2 * math.pi * self.freq * i / self.sample_rate))
                buf += struct.pack("<h", v)
                i += 1
            frames.append(bytes(buf))
            sent += self.frame_ms
        return frames


def build_providers(cfg) -> tuple:
    """Return (asr, llm, tts) according to cfg.*_provider. Default is mock."""
    from .providers_aws import BedrockLLM, PollyTTS, TranscribeASR  # lazy: boto3 only inside

    asr = TranscribeASR() if cfg.asr_provider in ("aws", "transcribe") else MockASR()
    llm = BedrockLLM(model_id=cfg.bedrock_model_id) if cfg.llm_provider in ("aws", "bedrock") else MockLLM()
    tts = PollyTTS() if cfg.tts_provider in ("aws", "polly") else MockTTS()
    return asr, llm, tts
