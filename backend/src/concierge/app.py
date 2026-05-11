from __future__ import annotations
import json
from collections import defaultdict
from dotenv import load_dotenv
from fastapi import FastAPI
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

load_dotenv()  # reads backend/.env so ANTHROPIC_API_KEY etc. are set before the SDK reads them

from concierge.agent import GiftAgent  # noqa: E402 — must import after load_dotenv

app = FastAPI(title="A2UI Gift Concierge")

_sessions: dict[str, GiftAgent] = defaultdict(lambda: GiftAgent())


class ChatBody(BaseModel):
    sessionId: str
    userMessage: str


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/chat")
async def chat(body: ChatBody) -> EventSourceResponse:
    agent = _sessions[body.sessionId]

    async def event_stream():
        # Catch agent failures (e.g. Anthropic 400/429, Gemini safety filter)
        # and surface them as a text bubble + clean `end`, otherwise the SSE
        # stream hangs and the client sits on a thinking indicator forever.
        try:
            async for ev in agent.turn(body.userMessage):
                if ev.kind == "end":
                    yield {"event": "end", "data": "{}"}
                elif ev.kind == "a2ui":
                    yield {"event": "a2ui", "data": json.dumps(ev.payload)}
                else:
                    yield {"event": "text", "data": json.dumps({"text": ev.payload})}
        except Exception as e:
            msg = f"⚠️ {type(e).__name__}: {e}"
            yield {"event": "text", "data": json.dumps({"text": msg})}
            yield {"event": "end", "data": "{}"}

    return EventSourceResponse(event_stream())
