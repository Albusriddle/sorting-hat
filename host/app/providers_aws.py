
"""AWS providers: Bedrock (LLM), Polly (TTS bridge), Transcribe (ASR, PCM-fed).

boto3 is imported lazily, so the host still runs in mock mode without it.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
from pathlib import Path

from .providers import Provider

DIMS = ("courage", "ambition", "wisdom", "loyalty")


class ProviderNotConfigured(RuntimeError):
    pass


class AsrUnavailable(RuntimeError):
    pass


def _client(service: str, region: str | None = None):
    try:
        import boto3
    except ImportError as exc:  # pragma: no cover - env dependent
        raise ProviderNotConfigured("boto3 not installed: pip install boto3") from exc
    return boto3.client(service, region_name=region or os.getenv("AWS_REGION", "ap-northeast-1"))


_JSON_FENCE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.S)


def parse_json_block(text: str) -> dict:
    """Extract the first JSON object from a model response (fenced or raw)."""
    m = _JSON_FENCE.search(text)
    raw = m.group(1) if m else text.strip()
    if not m:
        i, j = raw.find("{"), raw.rfind("}")
        if i >= 0 and j > i:
            raw = raw[i:j + 1]
    return json.loads(raw)


def chunk_pcm(pcm: bytes, sample_rate: int = 16000, frame_ms: int = 60) -> list[bytes]:
    """Slice 16-bit mono PCM into fixed 60 ms frames (device expects that)."""
    n = int(sample_rate * frame_ms / 1000) * 2
    frames = [pcm[i:i + n] for i in range(0, len(pcm), n)]
    if frames and len(frames[-1]) < n:
        frames[-1] = frames[-1] + b"\x00" * (n - len(frames[-1]))
    return frames or [b"\x00" * n]


class BedrockLLM(Provider):
    name = "bedrock"

    def __init__(self, model_id: str | None = None, region: str | None = None,
                 prompt_path: str | Path | None = None, max_tokens: int = 320,
                 temperature: float = 0.8):
        self.model_id = model_id or os.getenv("BEDROCK_MODEL_ID", "anthropic.claude-haiku")
        self.region = region
        self.max_tokens = max_tokens
        self.temperature = temperature
        default = Path(__file__).resolve().parent.parent / "persona" / "prompt.md"
        self.prompt = Path(prompt_path).read_text(encoding="utf-8") if prompt_path else \
            (default.read_text(encoding="utf-8") if default.exists() else "")

    async def health(self) -> bool:
        try:
            _client("bedrock-runtime", self.region)
            return True
        except Exception:
            return False

    async def complete(self, text: str) -> dict:
        def call() -> dict:
            client = _client("bedrock-runtime", self.region)
            resp = client.converse(
                modelId=self.model_id,
                system=[{"text": self.prompt}],
                messages=[{"role": "user", "content": [{"text": text}]}],
                inferenceConfig={"maxTokens": self.max_tokens, "temperature": self.temperature},
            )
            out = resp["output"]["message"]["content"][0]["text"]
            return parse_json_block(out)

        data = await asyncio.to_thread(call)
        return self._validate(data)

    @staticmethod
    def _validate(data: dict) -> dict:
        if data.get("refuse"):
            return {"refuse": True, "line": str(data.get("line", "这顶帽子不管这个。"))[:60]}
        if not isinstance(data.get("scores"), dict):
            raise ValueError("missing scores")
        scores = {}
        for d in DIMS:
            v = data["scores"].get(d, 0)
            try:
                scores[d] = max(0.0, min(10.0, float(v)))
            except (TypeError, ValueError):
                scores[d] = 0.0
        ev = data.get("evidence") or []
        if not isinstance(ev, list):
            ev = []
        clean = []
        for e in ev[:3]:
            if isinstance(e, dict) and str(e.get("quote", "")).strip():
                clean.append({"quote": str(e["quote"]).strip(),
                              "trait": str(e.get("trait", "courage")),
                              "why": str(e.get("why", ""))[:60]})
        return {"evidence": clean, "scores": scores,
                "line": str(data.get("line", ""))[:60]}


class PollyTTS(Provider):
    """Bridge-voice fallback only. NEVER used for the announcement line."""
    name = "polly"

    def __init__(self, voice_id: str | None = None, region: str | None = None,
                 sample_rate: int = 16000, frame_ms: int = 60):
        self.voice_id = voice_id or os.getenv("POLLY_VOICE_ID", "Zhiyu")
        self.region = region
        self.sample_rate = sample_rate
        self.frame_ms = frame_ms

    async def health(self) -> bool:
        try:
            _client("polly", self.region)
            return True
        except Exception:
            return False

    async def synth_async(self, text: str, max_chars: int = 600) -> list[bytes]:
        def call() -> bytes:
            client = _client("polly", self.region)
            r = client.synthesize_speech(
                Text=text[:max_chars], OutputFormat="pcm",
                SampleRate=str(self.sample_rate), VoiceId=self.voice_id)
            return r["AudioStream"].read()

        pcm = await asyncio.to_thread(call)
        return chunk_pcm(pcm, self.sample_rate, self.frame_ms)


class TranscribeASR(Provider):
    """Streaming ASR. Needs 16 kHz PCM; Opus decode is not wired yet."""
    name = "transcribe"

    def __init__(self, language: str = "zh-CN", region: str | None = None,
                 sample_rate: int = 16000):
        self.language = language
        self.region = region
        self.sample_rate = sample_rate

    async def health(self) -> bool:
        try:
            _client("transcribe", self.region)
            return True
        except Exception:
            return False

    async def final(self, text_hint: str = "", pcm: bytes | None = None) -> str:
        if not pcm:
            raise AsrUnavailable("no PCM: wire Opus decode before using Transcribe")
        def call() -> str:
            client = _client("transcribe", self.region)
            step = 3200  # 100 ms @16k/16bit

            def audio():
                for i in range(0, len(pcm), step):
                    yield {"AudioEvent": {"AudioChunk": pcm[i:i + step]}}

            resp = client.start_stream_transcription(
                LanguageCode=self.language, MediaSampleRateHertz=self.sample_rate,
                MediaEncoding="pcm", AudioStream=audio())
            final = ""
            for ev in resp["TranscriptResultStream"]:
                tr = ev.get("TranscriptEvent", {}).get("Transcript", {})
                for res in tr.get("Results", []):
                    if res.get("IsPartial"):
                        continue
                    alts = res.get("Alternatives") or [{}]
                    txt = "".join(i.get("Content", "") for i in alts[0].get("Items", []))
                    if txt:
                        final = txt
            return final

        text = await asyncio.to_thread(call)
        return text or text_hint or ""
