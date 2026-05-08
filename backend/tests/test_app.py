from fastapi.testclient import TestClient
from concierge.app import app

def test_health():
    client = TestClient(app)
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


import json
from unittest.mock import patch
from concierge.agent import AgentEvent


class _FakeAgent:
    def __init__(self, *_, **__):
        self.history = []
    async def turn(self, _msg):
        yield AgentEvent("text", "Three picks coming up.")
        yield AgentEvent("a2ui", {"component": "chip-group", "options": []})
        yield AgentEvent("end", None)


def test_chat_streams_sse_events():
    with patch("concierge.app.GiftAgent", _FakeAgent):
        client = TestClient(app)
        with client.stream("POST", "/chat",
                           json={"sessionId": "s1", "userMessage": "hi"}) as r:
            assert r.status_code == 200
            body = "".join(chunk for chunk in r.iter_text())
        assert "event: text" in body
        assert "event: a2ui" in body
        assert "event: end" in body
