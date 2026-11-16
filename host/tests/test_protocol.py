import pytest
from app import protocol


def test_ready_shape():
    m = protocol.ready("s-1")
    assert m["type"] == "ready" and m["sid"] == "s-1"
    assert m["audio"]["in"].startswith("pcm16/")
    assert "16000" in m["audio"]["out"]
    assert m["budget_ms"] == 1240


def test_error_codes_whitelist():
    assert protocol.error("asr_timeout")["code"] == "asr_timeout"
    with pytest.raises(AssertionError):
        protocol.error("nope")


def test_result_requires_known_house():
    assert protocol.result("courage", ["q"], "line", {})["house"] == "courage"
    with pytest.raises(AssertionError):
        protocol.result("gryffindor", ["q"], "line", {})


def test_audio_frame_header():
    b = protocol.audio_frame(7, b"abc")
    assert b[0] == 0x02 and int.from_bytes(b[1:5], "big") == 7 and b[5:] == b"abc"
