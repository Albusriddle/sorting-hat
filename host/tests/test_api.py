from fastapi.testclient import TestClient
from app.admin_app import admin_app
from app.config import settings

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
