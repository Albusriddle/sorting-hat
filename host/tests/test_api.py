from fastapi.testclient import TestClient
from app.admin_app import admin_app
from app.config import settings
from app.state import STATE

client = TestClient(admin_app)
H = {"X-Admin-Token": settings.admin_token}


def test_healthz():
    assert client.get("/healthz").json()["ok"] is True


def test_replay_requires_token():
    assert client.post("/v1/replay", json={}).status_code == 401


def test_replay_returns_house():
    r = client.post("/v1/replay", json={"text": "我想赢，我要第一"}, headers=H)
    assert r.status_code == 200
    body = r.json()
    assert body["house"] in ("courage", "ambition", "wisdom", "loyalty")
    assert body["provider"] in ("mock", "mock-llm")


def test_halt_roundtrip():
    assert client.post("/v1/halt", json={"mode": "halt_new"}, headers=H).json()["halt"] == "halt_new"
    assert client.post("/v1/halt", json={"mode": "none"}, headers=H).json()["halt"] == "none"


def test_config_rejects_invalid_silence_pair():
    old = (settings.silence_ms, settings.silence_bye_ms)
    r = client.post("/v1/config",
                    json={"silence_ms": 15000, "silence_bye_ms": 15000}, headers=H)
    assert r.status_code == 400
    assert (settings.silence_ms, settings.silence_bye_ms) == old


def test_config_applies_valid_pair():
    old = (settings.silence_ms, settings.silence_bye_ms)
    try:
        r = client.post("/v1/config",
                        json={"silence_ms": 12000, "silence_bye_ms": 20000}, headers=H)
        assert r.status_code == 200
        assert settings.silence_ms == 12000 and settings.silence_bye_ms == 20000
    finally:
        settings.silence_ms, settings.silence_bye_ms = old


def test_config_rejects_out_of_range_rms():
    old = settings.min_audio_rms
    r = client.post("/v1/config", json={"min_audio_rms": -1}, headers=H)
    assert r.status_code == 400
    assert settings.min_audio_rms == old


def test_config_does_not_pollute_state():
    old_cfg = dict(STATE.config)
    old = (settings.silence_ms, settings.silence_bye_ms)
    try:
        client.post("/v1/config", json={"silence_ms": 12000, "silence_bye_ms": 20000}, headers=H)
    finally:
        settings.silence_ms, settings.silence_bye_ms = old
        STATE.config.clear()
        STATE.config.update(old_cfg)
    assert STATE.config == old_cfg


def test_selfcheck_masks_tokens():
    r = client.get("/v1/selfcheck", headers=H)
    assert r.status_code == 200
    eff = r.json()["effective"]
    assert eff["balance_active"] is False
    assert eff["device_token"].startswith("***")
    assert "dev-token" not in eff["device_token"]


def test_selfcheck_requires_token():
    assert client.get("/v1/selfcheck").status_code == 401
