"""No-game smoke for the real LangGraph + official Codex SDK model path.

The smoke invokes both child roles with ChatGPT-managed Codex authentication.
Only the deterministic game boundary is fake, and it emits no input.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable

from langgraph.checkpoint.memory import InMemorySaver

from agent_subgraphs import AgentRuntime
from codex_sdk_client import CodexAgentClient
from goal_graph import build_goal_graph, run_goal


class SmokeGameTools:
    def __init__(self) -> None:
        self.observations = [
            {"screen_type": "PLAY", "summary": "synthetic safe play state"},
            {"screen_type": "RUN_END", "summary": "synthetic run end"},
        ]

    def prepare(self) -> dict:
        return {"verified": True, "run_id": "oauth-smoke", "entry_only": False}

    def observe(self) -> dict:
        return self.observations.pop(0)

    def menu_action(self, action: str, click=None) -> dict:
        raise AssertionError("smoke never enters menu navigation")

    def mark_in_game(self) -> None:
        return None

    def submit_direction(self, direction: str, latency_ms: float) -> bool:
        return direction in {"N", "NE", "E", "SE", "S", "SW", "W", "NW", "HOLD"}

    def control_window(self, seconds: float) -> dict:
        return {"safe": seconds == 2.0, "evidence": ["smoke-control"]}

    def select_level_up(self, option: int) -> dict:
        raise AssertionError("smoke observation never enters LEVEL_UP")

    def evaluate(self, goal: str, run_id: str) -> dict:
        return {
            "status": "achieved",
            "reason": "both SDK child roles completed with deterministic tools",
            "evidence": ["smoke-outcome"],
        }

    def evaluate_entry(self, run_id: str) -> dict:
        raise AssertionError("smoke is not entry-only")

    def neutralize(self) -> None:
        return None


async def run_smoke(
    *,
    codex_factory: Callable[..., CodexAgentClient] = CodexAgentClient,
) -> dict:
    """Exercise both child agents under one SDK lifecycle without game I/O."""

    tools = SmokeGameTools()
    runtime = AgentRuntime.from_checkpoint(
        {}, tools, codex_factory=codex_factory
    )
    graph = build_goal_graph(InMemorySaver())
    try:
        await runtime.codex.start()
        return await run_goal(
            graph,
            "Prove the leader and follower complete an official SDK smoke.",
            "oauth-smoke",
            runtime,
        )
    finally:
        try:
            tools.neutralize()
        finally:
            await runtime.codex.close()


def main() -> int:
    result = asyncio.run(run_smoke())
    print(json.dumps({
        "status": result["status"],
        "reason": result["reason"],
        "evidence": result["evidence"],
        "authentication": "ChatGPT Pro OAuth via official Codex SDK",
    }))
    return 0 if result["status"] == "achieved" else 2


if __name__ == "__main__":
    raise SystemExit(main())
