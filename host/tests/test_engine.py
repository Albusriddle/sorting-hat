import asyncio
import pytest
from app import engine as eng
from app.engine import SessionEngine
from app.providers import MockASR, MockLLM, MockTTS
from app.state import AppState


class SlowASR(MockASR):
    async def final(self, text_hint=""):
        await asyncio.sleep(0.2)
        return "慢"


class FastTTS(MockTTS):
    def synth(self, text, max_ms=120):
        return MockTTS().synth(text, max_ms)


@pytest.mark.asyncio
async def test_happy_path_events():
    sent = []

    async def emit(m):
        sent.append(m)

    st = AppState()
    e = SessionEngine(MockASR("我最想要的是赢"), MockLLM(), FastTTS(), st)
    out = await e.run(emit, "我最想要的是赢")
    kinds = [m if isinstance(m, (bytes, bytearray)) else m.get("type") for m in sent]
    assert "tts" in kinds and "result" in kinds
    assert kinds.count("result") == 1
    assert any(isinstance(m, (bytes, bytearray)) and m[0] == 0x02 for m in sent)
    assert out["latency"]["host_ms"] >= 0
    assert out["verdict"]["house"] in ("courage", "ambition", "wisdom", "loyalty")


@pytest.mark.asyncio
async def test_asr_timeout_falls_back(monkeypatch):
    monkeypatch.setattr(eng.settings, "asr_timeout_ms", 10)
    sent = []

    async def emit(m):
        sent.append(m)

    e = SessionEngine(SlowASR(), MockLLM(), FastTTS(), AppState())
    out = await e.run(emit, "")
    assert "asr_timeout" in out["degrade"]
