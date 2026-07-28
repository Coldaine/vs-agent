"""Behavioral tests for the isolated leader and follower child graphs."""

from __future__ import annotations

import inspect
import sys
import unittest
from dataclasses import fields
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "spine"))

from codex_sdk_client import CodexInvocation  # noqa: E402
import agent_subgraphs  # noqa: E402


class RecordingCodex:
    def __init__(self, *, thread_bindings: dict[str, str] | None = None) -> None:
        self.calls: list[dict] = []
        self._thread_bindings = dict(thread_bindings or {})

    @property
    def thread_bindings(self) -> dict[str, str]:
        return dict(self._thread_bindings)

    async def invoke(
        self,
        role: str,
        prompt: str,
        schema: dict,
        image_path: Path | None = None,
        thread_id: str | None = None,
    ) -> CodexInvocation:
        self.calls.append({
            "role": role,
            "prompt": prompt,
            "schema": schema,
            "image_path": image_path,
            "thread_id": thread_id,
        })
        assigned_thread = thread_id or f"{role}-thread"
        self._thread_bindings[role] = assigned_thread
        if role == "leader" and schema is agent_subgraphs.MENU_LEADER_SCHEMA:
            payload = {
                "screen": "CHARACTER_SELECT",
                "action": "confirm",
                "click": None,
                "ready_for_run": False,
                "reason": "advance",
            }
        elif role == "leader":
            payload = {"intent": "farm", "option": None, "reason": "open lane"}
        else:
            payload = {"direction": "NE", "confidence": 0.8, "reason": "clear"}
        return CodexInvocation(
            payload=payload,
            thread_id=assigned_thread,
            turn_id=f"{role}-turn-{len(self.calls)}",
            usage={"input_tokens": 7, "output_tokens": 3},
        )


class AgentSubgraphTests(unittest.IsolatedAsyncioTestCase):
    def test_agent_runtime_restores_only_typed_role_checkpoint_bindings(self) -> None:
        constructed_with: list[dict[str, str]] = []

        def codex_factory(*, thread_bindings):
            constructed_with.append(dict(thread_bindings))
            return RecordingCodex(thread_bindings=thread_bindings)

        tools = object()
        runtime = agent_subgraphs.AgentRuntime.from_checkpoint(
            {
                "leader_codex_thread_id": "leader-prior",
                "follower_codex_thread_id": "follower-prior",
            },
            tools,
            codex_factory=codex_factory,
        )

        self.assertEqual(
            constructed_with,
            [{"leader": "leader-prior", "follower": "follower-prior"}],
        )
        self.assertIs(runtime.tools, tools)
        self.assertEqual(
            runtime.codex.thread_bindings,
            {"leader": "leader-prior", "follower": "follower-prior"},
        )

    def test_agent_runtime_rejects_duplicate_or_ambiguous_checkpoint_bindings(self) -> None:
        factory_calls = 0

        def codex_factory(*, thread_bindings):
            nonlocal factory_calls
            factory_calls += 1
            return RecordingCodex(thread_bindings=thread_bindings)

        invalid_states = [
            {
                "leader_codex_thread_id": "shared",
                "follower_codex_thread_id": "shared",
            },
            {
                "leader_codex_thread_id": "leader-prior",
                "follower_codex_thread_id": None,
                "thread_bindings": {"leader": "different"},
            },
        ]
        for state in invalid_states:
            with self.subTest(state=state):
                with self.assertRaisesRegex(ValueError, "checkpoint.*binding"):
                    agent_subgraphs.AgentRuntime.from_checkpoint(
                        state,
                        object(),
                        codex_factory=codex_factory,
                    )

        self.assertEqual(factory_calls, 0)

    def test_builders_return_separate_compiled_graphs_with_disjoint_schemas(self) -> None:
        leader = agent_subgraphs.build_leader_subgraph()
        follower = agent_subgraphs.build_follower_subgraph()

        self.assertIsNot(leader, follower)
        self.assertEqual(leader.name, "leader_agent")
        self.assertEqual(follower.name, "follower_agent")
        leader_input = set(leader.get_input_jsonschema()["properties"])
        follower_input = set(follower.get_input_jsonschema()["properties"])
        leader_output = set(leader.get_output_jsonschema()["properties"])
        follower_output = set(follower.get_output_jsonschema()["properties"])
        self.assertTrue(leader_input.isdisjoint(follower_input))
        self.assertTrue(leader_output.isdisjoint(follower_output))
        self.assertIsNone(leader.checkpointer)
        self.assertIsNone(follower.checkpointer)

    async def test_leader_invokes_only_the_leader_role_and_reuses_its_thread(self) -> None:
        codex = RecordingCodex()
        graph = agent_subgraphs.build_leader_subgraph()
        runtime = agent_subgraphs.AgentModelRuntime(codex=codex)
        first = await graph.ainvoke(
            {
                "leader_goal": "survive",
                "leader_observation": {
                    "screen_type": "PLAY",
                    "image_path": "frame.jpg",
                },
                "leader_eval_contract": {"stage": "Mad Forest"},
                "leader_decision_kind": "gameplay",
                "leader_menu_steps_left": None,
                "leader_thread_id": None,
            },
            context=runtime,
        )
        second = await graph.ainvoke(
            {
                "leader_goal": "survive",
                "leader_observation": {"screen_type": "PLAY"},
                "leader_eval_contract": {"stage": "Mad Forest"},
                "leader_decision_kind": "gameplay",
                "leader_menu_steps_left": None,
                "leader_thread_id": first["leader_thread_id"],
            },
            context=runtime,
        )

        self.assertEqual([call["role"] for call in codex.calls], ["leader", "leader"])
        self.assertIs(codex.calls[0]["schema"], agent_subgraphs.LEADER_SCHEMA)
        self.assertEqual(codex.calls[0]["image_path"], Path("frame.jpg"))
        self.assertIsNone(codex.calls[0]["thread_id"])
        self.assertEqual(codex.calls[1]["thread_id"], "leader-thread")
        self.assertEqual(second["leader_decision"]["intent"], "farm")
        self.assertEqual(second["leader_turn_id"], "leader-turn-2")

    async def test_menu_leader_selects_the_menu_schema_and_forwards_the_image(self) -> None:
        codex = RecordingCodex()
        result = await agent_subgraphs.build_leader_subgraph().ainvoke(
            {
                "leader_goal": "reach the HUD",
                "leader_observation": {
                    "screen_type": "MENU",
                    "ocr_hint": "unreliable",
                    "image_path": "menu.jpg",
                },
                "leader_eval_contract": {"character": "Antonio"},
                "leader_decision_kind": "menu",
                "leader_menu_steps_left": 4,
                "leader_thread_id": None,
            },
            context=agent_subgraphs.AgentModelRuntime(codex=codex),
        )

        self.assertIs(codex.calls[0]["schema"], agent_subgraphs.MENU_LEADER_SCHEMA)
        self.assertEqual(codex.calls[0]["image_path"], Path("menu.jpg"))
        self.assertIn("Menu steps remaining: 4", codex.calls[0]["prompt"])
        self.assertEqual(result["leader_decision"]["action"], "confirm")

    async def test_follower_invokes_only_the_follower_role_and_reuses_its_thread(self) -> None:
        codex = RecordingCodex()
        graph = agent_subgraphs.build_follower_subgraph()
        runtime = agent_subgraphs.AgentModelRuntime(codex=codex)
        first = await graph.ainvoke(
            {
                "follower_goal": "survive",
                "follower_observation": {
                    "screen_type": "PLAY",
                    "image_path": "play.jpg",
                },
                "follower_leader_decision": {
                    "intent": "farm",
                    "option": None,
                    "reason": "safe",
                },
                "follower_thread_id": None,
            },
            context=runtime,
        )
        second = await graph.ainvoke(
            {
                "follower_goal": "survive",
                "follower_observation": {"screen_type": "PLAY"},
                "follower_leader_decision": first.get(
                    "follower_leader_decision",
                    {"intent": "farm", "option": None, "reason": "safe"},
                ),
                "follower_thread_id": first["follower_thread_id"],
            },
            context=runtime,
        )

        self.assertEqual(
            [call["role"] for call in codex.calls], ["follower", "follower"]
        )
        self.assertIs(codex.calls[0]["schema"], agent_subgraphs.FOLLOWER_SCHEMA)
        self.assertEqual(codex.calls[0]["image_path"], Path("play.jpg"))
        self.assertIsNone(codex.calls[0]["thread_id"])
        self.assertEqual(codex.calls[1]["thread_id"], "follower-thread")
        self.assertEqual(second["follower_proposal"]["direction"], "NE")
        self.assertEqual(second["follower_turn_id"], "follower-turn-2")

    def test_child_runtime_and_builder_interfaces_exclude_game_tools(self) -> None:
        self.assertEqual(
            [field.name for field in fields(agent_subgraphs.AgentModelRuntime)],
            ["codex"],
        )
        self.assertEqual(
            list(inspect.signature(agent_subgraphs.build_leader_subgraph).parameters),
            [],
        )
        self.assertEqual(
            list(inspect.signature(agent_subgraphs.build_follower_subgraph).parameters),
            [],
        )
        self.assertIs(
            agent_subgraphs.build_leader_subgraph().context_schema,
            agent_subgraphs.AgentModelRuntime,
        )
        self.assertIs(
            agent_subgraphs.build_follower_subgraph().context_schema,
            agent_subgraphs.AgentModelRuntime,
        )


if __name__ == "__main__":
    unittest.main()
