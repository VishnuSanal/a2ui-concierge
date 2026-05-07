from __future__ import annotations
from typing import Any, AsyncIterator
import json
from anthropic import AsyncAnthropic
from concierge.prompts import SYSTEM_PROMPT
from concierge.tools import TOOL_SCHEMAS, run_tool

MODEL = "claude-sonnet-4-6"


class AgentEvent:
    def __init__(self, kind: str, payload: Any):
        self.kind = kind  # "text" | "a2ui" | "end"
        self.payload = payload


class GiftAgent:
    def __init__(self, client: AsyncAnthropic | None = None):
        self.client = client or AsyncAnthropic()
        self.history: list[dict[str, Any]] = []

    async def turn(self, user_message: str) -> AsyncIterator[AgentEvent]:
        self.history.append({"role": "user", "content": user_message})

        while True:
            response = await self.client.messages.create(
                model=MODEL,
                max_tokens=2048,
                system=[{
                    "type": "text",
                    "text": SYSTEM_PROMPT,
                    "cache_control": {"type": "ephemeral"},
                }],
                tools=TOOL_SCHEMAS,
                messages=self.history,
            )

            assistant_blocks: list[dict[str, Any]] = []
            tool_uses: list[dict[str, Any]] = []

            for block in response.content:
                if block.type == "text":
                    assistant_blocks.append({"type": "text", "text": block.text})
                    if block.text.strip():
                        yield AgentEvent("text", block.text)
                elif block.type == "tool_use":
                    assistant_blocks.append({
                        "type": "tool_use", "id": block.id,
                        "name": block.name, "input": block.input,
                    })
                    tool_uses.append({"id": block.id, "name": block.name, "input": block.input})

            self.history.append({"role": "assistant", "content": assistant_blocks})

            if response.stop_reason != "tool_use":
                yield AgentEvent("end", None)
                return

            tool_results: list[dict[str, Any]] = []
            for tu in tool_uses:
                output = run_tool(tu["name"], tu["input"])
                if "_a2ui" in output:
                    yield AgentEvent("a2ui", output["_a2ui"])
                    tool_results.append({
                        "type": "tool_result", "tool_use_id": tu["id"],
                        "content": json.dumps({"rendered": True}),
                    })
                else:
                    tool_results.append({
                        "type": "tool_result", "tool_use_id": tu["id"],
                        "content": json.dumps(output),
                    })
            self.history.append({"role": "user", "content": tool_results})
