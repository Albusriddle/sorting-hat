import math
import struct

import pytest

from app import opus_codec
from app.audio import SessionAudio

pytestmark = pytest.mark.skipif(not opus_codec.available(), reason="libopus unavailable")


def _sine(samples: int = 960, freq: float = 300.0, rate: int = 16000) -> bytes:
    buf = bytearray()
    for i in range(samples):
        buf += struct.pack("<h", int(3000 * math.sin(2 * math.pi * freq * i / rate)))
    return bytes(buf)


def _encode(pcm: bytes, samples: int = 960) -> bytes:
    return opus_codec.encode_pcm(pcm, samples)


def test_decode_roundtrip():
    frame = _encode(_sine())
    pcm = opus_codec.decode(frame)
    assert len(pcm) == 1920  # 960 samples * 2 bytes


def test_empty_frame_is_silence():
    assert len(opus_codec.decode(b"")) == 1920


def test_session_audio_accepts_opus_and_pcm():
    a = SessionAudio()
    a.push_opus(_encode(_sine()))
    assert a.decoded == 1 and len(a.pcm()) == 1920
    a.push_pcm(b"\x00" * 960)
    assert len(a.pcm()) == 2880


def test_session_audio_caps_buffer():
    a = SessionAudio(max_seconds=1)          # 32000 bytes
    a.push_pcm(b"\x00" * 40000)
    assert len(a.pcm()) == 32000
