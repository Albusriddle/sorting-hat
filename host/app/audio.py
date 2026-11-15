"""Per-session PCM buffer fed either by Opus decode (0x01) or raw PCM (0x04)."""
from __future__ import annotations

from . import opus_codec

MAX_SECONDS = 120
BYTES_PER_SEC = 16000 * 2  # 16 kHz, 16-bit mono


class SessionAudio:
    def __init__(self, max_seconds: int = MAX_SECONDS):
        self.max_bytes = max_seconds * BYTES_PER_SEC
        self._buf = bytearray()
        self.frames = 0
        self.decoded = 0
        self.dropped = 0

    def reset(self) -> None:
        self._buf.clear()
        self.frames = 0
        self.decoded = 0
        self.dropped = 0

    def _append(self, pcm: bytes) -> None:
        if not pcm:
            return
        room = self.max_bytes - len(self._buf)
        if room <= 0:
            self.dropped += 1
            return
        self._buf.extend(pcm[:room])

    def push_opus(self, frame: bytes) -> None:
        self.frames += 1
        pcm = opus_codec.decode(frame)
        if pcm:
            self.decoded += 1
            self._append(pcm)

    def push_pcm(self, pcm: bytes) -> None:
        self._append(pcm)

    def pcm(self) -> bytes:
        return bytes(self._buf)

    def stats(self) -> dict:
        return {"bytes": len(self._buf), "frames": self.frames,
                "decoded": self.decoded, "dropped": self.dropped,
                "opus": opus_codec.available()}
