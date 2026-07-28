"""No-game smoke for the real LangGraph + ChatGPT Pro OAuth model path.

This invokes both the leader and follower as ``gpt-5.6-luna`` through Codex
OAuth, but uses deterministic in-memory game tools and emits no input.
"""

from __future__ import annotations

import json

from langgraph.checkpoint.memory import InMemorySaver

from goal_graph import build_goal_graph, initial_state
from oauth_codex import CodexOAuthRunner


class SmokeGameTools:
    def __init__(self) -> None:
        self.observations = [
            {"screen_type": "PLAY", "summary": "synthetic safe play state"},
            {"screen_type": "RUN_END", "summary": "synthetic run end"},
        ]

    def prepare(self) -> dict:
        return {"verified": True, "run_id": "oauth-smoke"}

    def observe(self) -> dict:
        return self.observations.pop(0)

    def submit_direction(self, direction: str, latency_ms: float) -> bool:
        return direction in {"N", "NE", "E", "SE", "S", "SW", "W", "NW", "HOLD"}

    def control_window(self, seconds: float) -> dict:
        return {"safe": seconds == 2.0, "evidence": ["smoke-control"]}

    def select_level_up(self, option: int) -> dict:
        raise AssertionError("smoke observation never enters LEVEL_UP")

    def evaluate(self, goal: str, run_id: str) -> dict:
        return {
            "status": "achieved",
            "reason": "both OAuth roles completed and deterministic tools evaluated",
            "evidence": ["smoke-outcome"],
        }

    def neutralize(self) -> None:
        return None


def run_smoke(model_runner=None) -> dict:
    runner = model_runner or CodexOAuthRunner()
    graph = build_goal_graph(runner, SmokeGameTools(), InMemorySaver())
    return graph.invoke(
        initial_state(
            "Prove the LangGraph leader and follower can complete an OAuth-only smoke."
        ),
        {"configurable": {"thread_id": "oauth-smoke"}, "recursion_limit": 30},
    )


def main() -> int:
    result = run_smoke()
    print(json.dumps({
        "status": result["status"],
        "reason": result["reason"],
        "evidence": result["evidence"],
        "authentication": "ChatGPT Pro OAuth via Codex CLI",
        "leader_model": "gpt-5.6-luna",
        "follower_model": "gpt-5.6-luna",
    }))
    return 0 if result["status"] == "achieved" else 2


if __name__ == "__main__":
    raise SystemExit(main())
