import json
import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.device_app import device_app
from app.state import STATE

client = TestClient(device_app)
TOKEN = settings.device_token
URL = f"/v1/voice?token={TOKEN}"


def pcm(value: int, samples: int = 320) -> bytes:
    return b"\x04" + (0).to_bytes(4, "big") + (value.to_bytes(2, "little", signed=True) * samples)


def test_text_path_sets_house(monkeypatch):
    with client.websocket_connect(URL, subprotocols=["sortinghat.voice.v1"]) as ws:
        assert ws.receive_json()["type"] == "ready"
        ws.send_json({"type": "listen", "state": "start"})
        ws.send_json({"type": "text", "text": "我在乎身边的人，他们需要我的时候我不会缺席。"})
        ws.send_bytes(pcm(1000))
        ws.send_json({"type": "vad", "ev": "speech_end"})
        seen = []
        for _ in range(400):
            m = ws.receive()
            if isinstance(m, (bytes, bytearray)) or "bytes" in m:
                continue
            d = json.loads(m["text"])
            seen.append(d["type"])
            if d["type"] == "result":
                assert d["house"] == "loyalty"
                assert d.get("scores")
                return
        raise AssertionError(f"no result, saw {seen}")


def test_zero_audio_gets_no_result():
    with client.websocket_connect(URL, subprotocols=["sortinghat.voice.v1"]) as ws:
        ws.receive_json()
        ws.send_json({"type": "listen", "state": "start"})
        ws.send_bytes(b"\x04" + b"\x00\x00\x00\x00" + b"\x00" * 640)
        ws.send_json({"type": "vad", "ev": "speech_end"})
        kinds = []
        for _ in range(400):
            m = ws.receive()
            if "bytes" in m:
                continue
            d = json.loads(m["text"])
            kinds.append(d["type"])
            if d["type"] == "result":
                raise AssertionError("zero audio must not produce result")
            if d["type"] == "tts" and d.get("state") == "stop" and kinds.count("tts") >= 2:
                return
        raise AssertionError(f"no stop, saw {kinds}")


def test_halt_new_blocks_session():
    STATE.halt = "halt_new"
    try:
        with client.websocket_connect(URL, subprotocols=["sortinghat.voice.v1"]) as ws:
            ws.receive_json()
            ws.send_json({"type": "listen", "state": "start"})
            d = ws.receive_json()
            assert d["type"] == "error" and d["code"] == "rate_limited"
    finally:
        STATE.halt = "none"


def test_auth_rejects_wrong_token():
    with pytest.raises(Exception):
        with client.websocket_connect("/v1/voice?token=wrong",
                                      subprotocols=["sortinghat.voice.v1"]) as ws:
            ws.receive_json()


def _run_one(ws, text: str) -> dict:
    ws.send_json({"type": "listen", "state": "start"})
    ws.send_json({"type": "text", "text": text})
    ws.send_bytes(pcm(1000))
    ws.send_json({"type": "vad", "ev": "speech_end"})
    for _ in range(400):
        m = ws.receive()
        if "bytes" in m:
            continue
        d = json.loads(m["text"])
        if d["type"] == "result":
            return d
    raise AssertionError("no result")


def test_two_sessions_one_connection_after_bye_done():
    """bye{done} 只结算本次、不断连接；两次会话应各落一行且都带 ttfc。"""
    from app.metrics import tail
    import time as _t

    before = len(tail(200))
    with client.websocket_connect(URL, subprotocols=["sortinghat.voice.v1"]) as ws:
        ws.receive_json()
        r1 = _run_one(ws, "我在乎身边的人，他们需要我的时候我不会缺席。")
        assert r1["house"] == "loyalty"
        ws.send_json({"type": "bye", "reason": "done",
                      "dev_ts": {"t_arm": 1, "t0": 10, "t5a": 11, "t5b": 12}})
        r2 = _run_one(ws, "我最怕输，但我更怕自己在关键时候退缩。")
        assert r2["house"] == "courage"
        ws.send_json({"type": "bye", "reason": "done",
                      "dev_ts": {"t_arm": 20, "t0": 30, "t5a": 31, "t5b": 32}})
    _t.sleep(0.3)
    rows = tail(200)
    assert len(rows) >= before + 2
    assert rows[-2].get("ttfc_ms") == 2 and rows[-1].get("ttfc_ms") == 2
