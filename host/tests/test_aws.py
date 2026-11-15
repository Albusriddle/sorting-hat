import pytest
from app.providers_aws import BedrockLLM, chunk_pcm, parse_json_block
from app.providers import MockASR, MockLLM, MockTTS, build_providers
from app.config import settings


def test_parse_fenced_and_raw():
    assert parse_json_block('```json\n{"scores":{"courage":1}}\n```')["scores"]["courage"] == 1
    assert parse_json_block('ok: {"scores":{"wisdom":2}} done')["scores"]["wisdom"] == 2


def test_parse_invalid_raises():
    with pytest.raises(Exception):
        parse_json_block("not json at all")


def test_chunk_pcm_60ms():
    # 16000 Hz * 16 bit mono * 1.2 s = 38400 bytes -> 20 frames of 60 ms
    frames = chunk_pcm(b"\x00" * 38400, 16000, 60)
    assert len(frames) == 20
    assert all(len(f) == 1920 for f in frames)


def test_bedrock_validate_clamps_and_trims():
    out = BedrockLLM._validate({"scores": {"courage": 99, "ambition": -3, "wisdom": "x"},
                                "evidence": [{"quote": " 原话 ", "trait": "courage", "why": "w" * 200}],
                                "line": "l" * 200})
    assert out["scores"]["courage"] == 10.0
    assert out["scores"]["ambition"] == 0.0
    assert out["scores"]["wisdom"] == 0.0
    assert out["evidence"][0]["quote"] == "原话"
    assert len(out["line"]) <= 60


def test_factory_defaults_to_mock(monkeypatch):
    monkeypatch.setattr(settings, "asr_provider", "mock")
    monkeypatch.setattr(settings, "llm_provider", "mock")
    monkeypatch.setattr(settings, "tts_provider", "mock")
    asr, llm, tts = build_providers(settings)
    assert (type(asr), type(llm), type(tts)) == (MockASR, MockLLM, MockTTS)


def test_factory_selects_aws(monkeypatch):
    monkeypatch.setattr(settings, "asr_provider", "aws")
    monkeypatch.setattr(settings, "llm_provider", "aws")
    monkeypatch.setattr(settings, "tts_provider", "aws")
    asr, llm, tts = build_providers(settings)
    assert asr.name == "transcribe" and llm.name == "bedrock" and tts.name == "polly"
