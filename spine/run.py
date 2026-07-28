"""Run the LangGraph Vampire Survivors goal runtime.

Authentication is CHATGPT PRO OAUTH ONLY through the official Codex SDK. This
entry point does not accept an OpenAI API key, API endpoint, provider override,
or model override.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import uuid
from pathlib import Path

import yaml
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from agent_subgraphs import AgentRuntime
from codex_sdk_client import CodexAgentClient
from controller import Controller
from game_tools import SpineGameTools
from goal_graph import build_goal_graph, run_goal
from io_adapter import IOAdapter


DEFAULT_GOAL = (
    "Complete a fixed-condition Mad Forest run and produce deterministic "
    "evidence that survival reached at least 540 seconds."
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run the LangGraph leader/follower through ChatGPT Pro OAuth. "
            "OpenAI API keys and compatible HTTP APIs are forbidden."
        )
    )
    parser.add_argument("--goal", default=DEFAULT_GOAL)
    parser.add_argument(
        "--thread-id",
        default=None,
        help="Durable LangGraph thread to create or resume (default: generated)",
    )
    parser.add_argument("--retries", type=int, default=0)
    parser.add_argument(
        "--checkpoint",
        default="runtime/langgraph-goals.sqlite3",
        help="Local LangGraph checkpoint database",
    )
    parser.add_argument("--config", default="spine/config.yaml")
    parser.add_argument(
        "--attach",
        action="store_true",
        help=(
            "Attach to an already-live IN_GAME or LEVEL_UP screen; "
            "skip vision menu entry."
        ),
    )
    parser.add_argument(
        "--entry-only",
        action="store_true",
        help=(
            "Succeed when the vision leader reaches an in-game HUD; "
            "do not continue into survival scoring."
        ),
    )
    return parser


async def run_langgraph_goal(
    goal: str,
    *,
    thread_id: str,
    retries: int,
    checkpoint_path: str,
    config_path: str,
    attach: bool = False,
    entry_only: bool = False,
) -> dict:
    """Run one goal under one checkpoint-bound Codex SDK lifecycle."""

    cfg = yaml.safe_load(Path(config_path).read_text(encoding="utf-8"))
    io = IOAdapter(backend=os.environ.get("VS_IO_BACKEND", "auto"), config=cfg)
    controller = Controller(io, cfg)
    tools = SpineGameTools(
        cfg, io, controller, attach=attach, entry_only=entry_only
    )
    checkpoint = Path(checkpoint_path)
    checkpoint.parent.mkdir(parents=True, exist_ok=True)
    runtime = None

    try:
        async with AsyncSqliteSaver.from_conn_string(str(checkpoint)) as checkpointer:
            graph = build_goal_graph(checkpointer)
            config = {
                "configurable": {"thread_id": thread_id},
                "recursion_limit": 1000,
            }
            snapshot = await graph.aget_state(config)
            runtime = AgentRuntime.from_checkpoint(
                snapshot.values or {},
                tools,
                codex_factory=CodexAgentClient,
            )
            await runtime.codex.start()
            return await run_goal(
                graph,
                goal,
                thread_id,
                runtime,
                retries=retries,
            )
    finally:
        try:
            tools.neutralize()
        finally:
            try:
                if runtime is not None:
                    await runtime.codex.close()
            finally:
                tools.close()


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    thread_id = args.thread_id or f"goal-{uuid.uuid4()}"
    state = asyncio.run(
        run_langgraph_goal(
            args.goal,
            thread_id=thread_id,
            retries=args.retries,
            checkpoint_path=args.checkpoint,
            config_path=args.config,
            attach=args.attach,
            entry_only=args.entry_only,
        )
    )
    print(json.dumps({
        "thread_id": thread_id,
        "status": state["status"],
        "reason": state["reason"],
        "evidence": state["evidence"],
        "authentication": "ChatGPT Pro OAuth via official Codex SDK",
    }))
    return 0 if state["status"] == "achieved" else 2


if __name__ == "__main__":
    raise SystemExit(main())
