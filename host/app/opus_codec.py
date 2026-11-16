"""Opus decode with a Windows-friendly fallback.

`opuslib` needs libopus. On this machine pyogg ships `opus.dll`, so we point the
DLL search path at it before importing opuslib. If neither is available the
gateway still runs (it just cannot decode, and ASR falls back).
"""
from __future__ import annotations

import os
import sys

_DECODER = None
_ERROR: str | None = None


def _install_unraisable_filter() -> None:
    """opuslib's Decoder.__del__ raises when construction failed; keep logs clean."""
    import sys

    if getattr(sys, "_opus_filter_installed", False):
        return
    prev = sys.unraisablehook

    def hook(unraisable):  # pragma: no cover - interpreter shutdown path
        obj = repr(getattr(unraisable, "object", ""))
        if "Decoder" in obj or "opuslib" in obj:
            return
        prev(unraisable)

    sys.unraisablehook = hook
    sys._opus_filter_installed = True


_install_unraisable_filter()


def _atexit_close() -> None:  # pragma: no cover - interpreter shutdown
    """Drop the ctypes state before libopus is unloaded (opuslib __del__ bug)."""
    global _DECODER
    d, _DECODER = _DECODER, None
    if d is not None:
        try:
            del d.decoder_state
        except Exception:
            pass


import atexit

atexit.register(_atexit_close)


def _load_opuslib():
    global _ERROR
    try:
        import opuslib  # noqa: F401
        return opuslib
    except Exception as first:  # DLL missing
        try:
            import pyogg  # ships opus.dll on Windows
            d = os.path.dirname(pyogg.__file__)
            os.environ["PATH"] = d + os.pathsep + os.environ.get("PATH", "")
            if hasattr(os, "add_dll_directory"):
                try:
                    os.add_dll_directory(d)
                except Exception:
                    pass
            import opuslib
            return opuslib
        except Exception as second:
            _ERROR = f"{type(first).__name__}: {first} / {type(second).__name__}: {second}"
            return None


def available() -> bool:
    return _decoder() is not None


def error() -> str | None:
    return _ERROR


def _decoder():
    global _DECODER
    if _DECODER is not None:
        return _DECODER
    lib = _load_opuslib()
    if lib is None:
        return None
    try:
        _DECODER = lib.Decoder(16000, 1)
    except Exception as exc:  # pragma: no cover
        global _ERROR
        _ERROR = f"{type(exc).__name__}: {exc}"
        return None
    return _DECODER


FRAME_CANDIDATES = (960, 1920, 480, 2880, 5760)  # 60/120/30/180/360 ms @16 kHz


def decode(frame: bytes) -> bytes:
    """Decode one Opus packet to 16 kHz/16 bit mono PCM. Empty frame -> silence."""
    dec = _decoder()
    if dec is None:
        return b""
    if not frame:
        return b"\x00" * (960 * 2)  # DTX / lost packet placeholder
    for samples in FRAME_CANDIDATES:
        try:
            return dec.decode(frame, samples)
        except Exception:
            continue
    return b""


def encode_pcm(pcm: bytes, samples: int = 960) -> bytes:
    """Encode 16 kHz/16-bit mono PCM into one Opus packet (used by smoke/tests)."""
    lib = _load_opuslib()
    if lib is None:
        return b""
    try:
        enc = lib.Encoder(16000, 1, "audio")
        return enc.encode(pcm, samples)
    except Exception:
        return b""
