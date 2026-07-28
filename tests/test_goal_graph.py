"""Behavioral tests for the durable LangGraph goal runtime."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "spine"))

from langgraph.checkpoint.memory import InMemorySaver  # noqa: E402
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver  # noqa: E402

import agent_subgraphs  # noqa: E402
from codex_sdk_client import CodexInvocation  # noqa: E402
import goal_graph  # noqa: E402


class ScriptedModel:
    def __init__(self) -> None:
        self.roles: list[str] = []
        self.image_paths: list[tuple[str, object]] = []
        self.schemas: list[dict] = []
        self._thread_bindings: dict[str, str] = {}

    @property
    def thread_bindings(self) -> dict[str, str]:
        return dict(self._thread_bindings)

    async def invoke(
        self,
        role: str,
        prompt: str,
        schema: dict,
        image_path=None,
        thread_id: str | None = None,
    ) -> CodexInvocation:
        self.roles.append(role)
        self.image_paths.append((role, image_path))
        self.schemas.append(schema)
        if role == "leader":
            if schema is goal_graph.MENU_LEADER_SCHEMA or "Menu steps remaining" in prompt:
                payload = {
                    "screen": "CHARACTER_SELECT",
                    "action": "confirm",
                    "click": None,
                    "ready_for_run": False,
                    "reason": "advance",
                }
            elif "LEVEL_UP" in prompt:
                payload = {"intent": "choose upgrade", "option": 2, "reason": "damage"}
            else:
                payload = {
                    "intent": "farm open ground",
                    "option": None,
                    "reason": "safe growth",
                }
        else:
            payload = {"direction": "NE", "confidence": 0.8, "reason": "open lane"}
        assigned_thread = thread_id or f"{role}-thread"
        self._thread_bindings[role] = assigned_thread
        return CodexInvocation(
            payload=payload,
            thread_id=assigned_thread,
            turn_id=f"{role}-turn-{len(self.roles)}",
            usage=None,
        )


class ScriptedTools:
    def __init__(
        self,
        observations: list[dict],
        evaluation: dict | None = None,
        *,
        entry_only: bool = False,
        menu_steps_budget: int = 40,
    ) -> None:
        self.observations = list(observations)
        self.evaluation = evaluation or {
            "status": "achieved",
            "reason": "target proven",
            "evidence": ["outcome.json"],
        }
        self.entry_only = entry_only
        self.menu_steps_budget = menu_steps_budget
        self.calls: list[object] = []
        self.in_game = False

    def prepare(self) -> dict:
        self.calls.append("prepare")
        return {
            "run_id": "run-test",
            "verified": True,
            "entry_only": self.entry_only,
            "menu_steps_budget": self.menu_steps_budget,
            "eval_contract": {
                "character": "Antonio",
                "stage": "Mad Forest",
                "modifiers": {"arcanas": False},
            },
        }

    def observe(self) -> dict:
        self.calls.append("observe")
        return self.observations.pop(0)

    def menu_action(self, action: str, click=None) -> dict:
        self.calls.append(("menu_action", action, click))
        return {"ok": True, "evidence": [f"menu:{action}"]}

    def mark_in_game(self) -> None:
        self.calls.append("mark_in_game")
        self.in_game = True

    def submit_direction(self, direction: str, latency_ms: float) -> bool:
        self.calls.append(("submit_direction", direction, latency_ms))
        return direction in {"N", "NE", "E", "SE", "S", "SW", "W", "NW", "HOLD"}

    def control_window(self, seconds: float) -> dict:
        self.calls.append(("control_window", seconds))
        return {"safe": True, "evidence": ["tick-1"]}

    def select_level_up(self, option: int) -> dict:
        self.calls.append(("select_level_up", option))
        return {"selected": option, "evidence": ["level-up-1"]}

    def evaluate(self, goal: str, run_id: str) -> dict:
        self.calls.append(("evaluate", goal, run_id))
        return self.evaluation

    def evaluate_entry(self, run_id: str) -> dict:
        self.calls.append(("evaluate_entry", run_id))
        return {
            "status": "achieved",
            "reason": "vision reached in-game HUD under fixed eval contract",
            "evidence": ["entry-outcome.json"],
        }

    def neutralize(self) -> None:
        self.calls.append("neutralize")


class ScriptedCodex:
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
        image_path=None,
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
        if role == "leader":
            payload = {"intent": "farm", "option": None, "reason": "safe"}
        else:
            payload = {"direction": "NE", "confidence": 0.8, "reason": "clear"}
        return CodexInvocation(
            payload=payload,
            thread_id=assigned_thread,
            turn_id=f"{role}-turn-{len(self.calls)}",
            usage=None,
        )


class ParentSubgraphTests(unittest.IsolatedAsyncioTestCase):
    async def test_parent_resume_keeps_child_namespace_and_does_not_repeat_leader(self) -> None:
        codex = ScriptedCodex()
        tools = ScriptedTools([
            {"screen_type": "PLAY", "summary": "safe", "image_path": "frame.jpg"},
            {"screen_type": "RUN_END", "summary": "done"},
        ])
        checkpointer = InMemorySaver()
        graph = goal_graph.build_goal_graph(checkpointer, pause_after_leader=True)
        runtime = agent_subgraphs.AgentRuntime(codex=codex, tools=tools)
        config = {
            "configurable": {"thread_id": "child-resume"},
            "recursion_limit": 30,
        }

        paused = await graph.ainvoke(
            goal_graph.initial_state("finish", retries=0),
            config,
            context=runtime,
        )

        self.assertEqual(paused["phase"], "planned")
        self.assertEqual(paused["leader_codex_thread_id"], "leader-thread")
        self.assertEqual([call["role"] for call in codex.calls], ["leader"])
        namespaces = {
            item.config["configurable"].get("checkpoint_ns", "")
            for item in checkpointer.list(None)
            if item.config["configurable"].get("thread_id") == "child-resume"
        }
        self.assertTrue(any("leader" in namespace for namespace in namespaces))

        resumed = await graph.ainvoke(None, config, context=runtime)

        self.assertEqual(resumed["status"], "achieved")
        self.assertEqual(
            [call["role"] for call in codex.calls], ["leader", "follower"]
        )
        self.assertEqual(resumed["leader_codex_thread_id"], "leader-thread")
        self.assertEqual(resumed["follower_codex_thread_id"], "follower-thread")

    async def test_parent_neutralizes_all_binding_failures_before_sdk_resume(self) -> None:
        cases = [
            ("missing", "leader-prior", None, {}, RuntimeError),
            ("extra", None, None, {"leader": "unexpected"}, RuntimeError),
            (
                "cross-role",
                "leader-prior",
                None,
                {"follower": "leader-prior"},
                RuntimeError,
            ),
            ("duplicate", "shared", "shared", {}, ValueError),
        ]
        for name, leader_id, follower_id, runtime_bindings, error_type in cases:
            with self.subTest(name=name):
                codex = ScriptedCodex(thread_bindings=runtime_bindings)
                tools = ScriptedTools([{"screen_type": "PLAY", "summary": "safe"}])
                graph = goal_graph.build_goal_graph(InMemorySaver())
                state = goal_graph.initial_state("finish", retries=0)
                state["leader_codex_thread_id"] = leader_id
                state["follower_codex_thread_id"] = follower_id

                with self.assertRaisesRegex(error_type, "checkpoint"):
                    await graph.ainvoke(
                        state,
                        {"configurable": {"thread_id": f"binding-{name}"}},
                        context=agent_subgraphs.AgentRuntime(codex=codex, tools=tools),
                    )

                self.assertEqual(codex.calls, [])
                self.assertEqual(tools.calls[-1], "neutralize")


class GoalGraphTests(unittest.IsolatedAsyncioTestCase):
    async def test_play_cycle_uses_leader_then_follower_and_ends_on_evidence(self) -> None:
        model = ScriptedModel()
        tools = ScriptedTools([
            {"screen_type": "PLAY", "summary": "clear northeast", "image_path": "frame.jpg"},
            {"screen_type": "RUN_END", "summary": "run ended"},
        ])
        times = iter([10.0, 10.321])
        graph = goal_graph.build_goal_graph(InMemorySaver(), clock=lambda: next(times))

        result = await graph.ainvoke(
            goal_graph.initial_state("survive at least 9 minutes", retries=1),
            {"configurable": {"thread_id": "play-cycle"}, "recursion_limit": 30},
            context=agent_subgraphs.AgentRuntime(codex=model, tools=tools),
        )

        self.assertEqual(result["status"], "achieved")
        self.assertEqual(model.roles, ["leader", "follower"])
        submission = next(call for call in tools.calls if call[0] == "submit_direction")
        self.assertEqual(submission[:2], ("submit_direction", "NE"))
        self.assertAlmostEqual(submission[2], 321.0)
        self.assertIn(("control_window", 2.0), tools.calls)
        self.assertEqual(model.image_paths[-1], ("follower", Path("frame.jpg")))
        self.assertEqual(result["evidence"], ["tick-1", "outcome.json"])
        self.assertEqual(tools.calls[-1], "neutralize")

    async def test_menu_observation_routes_to_vision_leader_not_blocked(self) -> None:
        class MenuThenPlay(ScriptedModel):
            def __init__(self) -> None:
                super().__init__()
                self.menu_calls = 0

            async def invoke(self, role, prompt, schema, image_path=None, thread_id=None):
                if "Menu steps remaining" in prompt:
                    self.menu_calls += 1
                    self.roles.append(role)
                    self.schemas.append(schema)
                    if self.menu_calls == 1:
                        payload = {
                            "screen": "CHARACTER_SELECT",
                            "action": "confirm",
                            "click": None,
                            "ready_for_run": False,
                            "reason": "confirm antonio",
                        }
                    else:
                        payload = {
                        "screen": "IN_GAME",
                        "action": "wait",
                        "click": None,
                        "ready_for_run": True,
                        "reason": "hud visible",
                        }
                    assigned = thread_id or "leader-thread"
                    self._thread_bindings[role] = assigned
                    return CodexInvocation(payload, assigned, "menu-turn", None)
                return await super().invoke(role, prompt, schema, image_path, thread_id)

        model = MenuThenPlay()
        tools = ScriptedTools(
            [
                {
                    "screen_type": "MENU",
                    "screen_guess": "CHARACTER_SELECT",
                    "ocr_hint": "garbage",
                    "image_path": "menu.jpg",
                },
                {
                    "screen_type": "MENU",
                    "screen_guess": "UNKNOWN",
                    "ocr_hint": "still garbage",
                    "image_path": "menu2.jpg",
                },
            ],
            entry_only=True,
        )
        graph = goal_graph.build_goal_graph(InMemorySaver())

        result = await graph.ainvoke(
            goal_graph.initial_state("reach Mad Forest HUD", retries=0),
            {"configurable": {"thread_id": "menu-route"}, "recursion_limit": 40},
            context=agent_subgraphs.AgentRuntime(codex=model, tools=tools),
        )

        self.assertEqual(result["status"], "achieved")
        self.assertIn(("menu_action", "confirm", None), tools.calls)
        self.assertIn("mark_in_game", tools.calls)
        self.assertIn(("evaluate_entry", "run-test"), tools.calls)
        self.assertNotIn(("submit_direction", "NE", 0.0), tools.calls)
        self.assertTrue(
            any(schema is goal_graph.MENU_LEADER_SCHEMA for schema in model.schemas)
        )

    async def test_ocr_hint_alone_cannot_force_play_transition(self) -> None:
        model = ScriptedModel()
        tools = ScriptedTools(
            [
                {
                    "screen_type": "MENU",
                    "screen_guess": "CHARACTER_SELECT",
                    "ocr_hint": "IN_GAME 00:16 MAD FOREST",
                    "image_path": "menu.jpg",
                },
                {
                    "screen_type": "MENU",
                    "screen_guess": "CHARACTER_SELECT",
                    "ocr_hint": "IN_GAME 00:16 MAD FOREST",
                    "image_path": "menu2.jpg",
                },
            ],
            entry_only=True,
            menu_steps_budget=1,
        )
        graph = goal_graph.build_goal_graph(InMemorySaver())

        result = await graph.ainvoke(
            goal_graph.initial_state("reach HUD", retries=0),
            {"configurable": {"thread_id": "ocr-not-authority"}, "recursion_limit": 20},
            context=agent_subgraphs.AgentRuntime(codex=model, tools=tools),
        )

        # One menu action then budget exhausted — never promoted by OCR hint text.
        self.assertEqual(result["status"], "blocked")
        self.assertIn("menu step budget", result["reason"])
        self.assertNotIn("mark_in_game", tools.calls)

    async def test_menu_budget_exhaustion_neutralizes_and_blocks(self) -> None:
        class AlwaysMenu(ScriptedModel):
            async def invoke(self, role, prompt, schema, image_path=None, thread_id=None):
                self.roles.append(role)
                assigned = thread_id or "leader-thread"
                self._thread_bindings[role] = assigned
                return CodexInvocation({
                    "screen": "STAGE_SELECT",
                    "action": "down",
                    "click": None,
                    "ready_for_run": False,
                    "reason": "still looking",
                }, assigned, "menu-turn", None)

        model = AlwaysMenu()
        tools = ScriptedTools(
            [{"screen_type": "MENU", "image_path": f"m{i}.jpg"} for i in range(5)],
            entry_only=True,
            menu_steps_budget=2,
        )
        graph = goal_graph.build_goal_graph(InMemorySaver())

        result = await graph.ainvoke(
            goal_graph.initial_state("reach HUD", retries=0),
            {"configurable": {"thread_id": "budget"}, "recursion_limit": 30},
            context=agent_subgraphs.AgentRuntime(codex=model, tools=tools),
        )

        self.assertEqual(result["status"], "blocked")
        self.assertIn("budget", result["reason"])
        self.assertEqual(tools.calls[-1], "neutralize")

    async def test_level_up_routes_to_leader_without_calling_follower(self) -> None:
        model = ScriptedModel()
        tools = ScriptedTools([
            {"screen_type": "LEVEL_UP", "summary": "three options"},
            {"screen_type": "RUN_END", "summary": "run ended"},
        ])
        graph = goal_graph.build_goal_graph(InMemorySaver())

        result = await graph.ainvoke(
            goal_graph.initial_state("complete one run", retries=0),
            {"configurable": {"thread_id": "level-up"}, "recursion_limit": 30},
            context=agent_subgraphs.AgentRuntime(codex=model, tools=tools),
        )

        self.assertEqual(result["status"], "achieved")
        self.assertEqual(model.roles, ["leader"])
        self.assertIn(("select_level_up", 2), tools.calls)

    async def test_safety_fault_neutralizes_and_blocks_without_model_call(self) -> None:
        model = ScriptedModel()
        tools = ScriptedTools([{"screen_type": "SAFETY_FAULT", "summary": "capture lost"}])
        graph = goal_graph.build_goal_graph(InMemorySaver())

        result = await graph.ainvoke(
            goal_graph.initial_state("complete one run", retries=1),
            {"configurable": {"thread_id": "fault"}},
            context=agent_subgraphs.AgentRuntime(codex=model, tools=tools),
        )

        self.assertEqual(result["status"], "blocked")
        self.assertIn("capture lost", result["reason"])
        self.assertEqual(model.roles, [])
        self.assertEqual(tools.calls[-1], "neutralize")

    async def test_rejected_follower_direction_neutralizes_and_blocks(self) -> None:
        class InvalidFollower(ScriptedModel):
            async def invoke(self, role, prompt, schema, image_path=None, thread_id=None):
                if role == "follower":
                    self.roles.append(role)
                    assigned = thread_id or "follower-thread"
                    self._thread_bindings[role] = assigned
                    return CodexInvocation(
                        {"direction": "TELEPORT", "confidence": 1.0, "reason": "invalid"},
                        assigned,
                        "follower-turn",
                        None,
                    )
                return await super().invoke(role, prompt, schema, image_path, thread_id)

        model = InvalidFollower()
        tools = ScriptedTools([{"screen_type": "PLAY", "summary": "open"}])
        graph = goal_graph.build_goal_graph(InMemorySaver())

        result = await graph.ainvoke(
            goal_graph.initial_state("complete one run", retries=0),
            {"configurable": {"thread_id": "invalid-direction"}},
            context=agent_subgraphs.AgentRuntime(codex=model, tools=tools),
        )

        self.assertEqual(result["status"], "blocked")
        self.assertIn("TELEPORT", result["reason"])
        self.assertEqual(tools.calls[-1], "neutralize")

    async def test_not_met_evaluation_retries_only_within_budget(self) -> None:
        model = ScriptedModel()
        tools = ScriptedTools(
            [
                {"screen_type": "RUN_END", "summary": "first run"},
                {"screen_type": "RUN_END", "summary": "second run"},
            ],
            evaluation={"status": "not_met", "reason": "too short", "evidence": []},
        )
        graph = goal_graph.build_goal_graph(InMemorySaver())

        result = await graph.ainvoke(
            goal_graph.initial_state("survive 9 minutes", retries=1),
            {"configurable": {"thread_id": "retry-budget"}, "recursion_limit": 30},
            context=agent_subgraphs.AgentRuntime(codex=model, tools=tools),
        )

        self.assertEqual(result["status"], "not_met")
        self.assertEqual(result["retries_left"], 0)
        self.assertEqual(tools.calls.count("prepare"), 2)

    async def test_checkpoint_resume_continues_after_observation_without_repreparing(self) -> None:
        model = ScriptedModel()
        tools = ScriptedTools([
            {"screen_type": "PLAY", "summary": "safe"},
            {"screen_type": "RUN_END", "summary": "done"},
        ])
        graph = goal_graph.build_goal_graph(InMemorySaver(), pause_after_observe=True)
        config = {"configurable": {"thread_id": "resume"}, "recursion_limit": 30}
        runtime = agent_subgraphs.AgentRuntime(codex=model, tools=tools)

        paused = await graph.ainvoke(
            goal_graph.initial_state("finish", retries=0), config, context=runtime
        )
        self.assertEqual(paused["phase"], "observed")
        self.assertEqual(tools.calls.count("prepare"), 1)

        resumed = await graph.ainvoke(None, config, context=runtime)

        self.assertEqual(resumed["phase"], "observed")
        self.assertEqual(tools.calls.count("prepare"), 1)
        self.assertEqual(model.roles, ["leader", "follower"])

    async def test_sqlite_checkpoint_resumes_after_graph_is_rebuilt(self) -> None:
        model = ScriptedModel()
        tools = ScriptedTools([
            {"screen_type": "PLAY", "summary": "safe"},
            {"screen_type": "RUN_END", "summary": "done"},
        ])
        config = {"configurable": {"thread_id": "sqlite-resume"}, "recursion_limit": 30}
        with tempfile.TemporaryDirectory() as root:
            database = str(Path(root, "goals.sqlite3"))
            runtime = agent_subgraphs.AgentRuntime(codex=model, tools=tools)
            async with AsyncSqliteSaver.from_conn_string(database) as checkpointer:
                first_graph = goal_graph.build_goal_graph(
                    checkpointer, pause_after_observe=True
                )
                paused = await first_graph.ainvoke(
                    goal_graph.initial_state("finish", retries=0),
                    config,
                    context=runtime,
                )
                self.assertEqual(paused["phase"], "observed")

            async with AsyncSqliteSaver.from_conn_string(database) as checkpointer:
                rebuilt_graph = goal_graph.build_goal_graph(
                    checkpointer, pause_after_observe=True
                )
                resumed = await rebuilt_graph.ainvoke(None, config, context=runtime)

        self.assertEqual(resumed["phase"], "observed")
        self.assertEqual(tools.calls.count("prepare"), 1)
        self.assertEqual(model.roles, ["leader", "follower"])

    async def test_run_goal_uses_async_state_lookup_with_async_sqlite(self) -> None:
        model = ScriptedModel()
        tools = ScriptedTools([
            {"screen_type": "PLAY", "summary": "safe"},
            {"screen_type": "RUN_END", "summary": "done"},
        ])
        runtime = agent_subgraphs.AgentRuntime(codex=model, tools=tools)
        with tempfile.TemporaryDirectory() as root:
            database = str(Path(root, "run-goal.sqlite3"))
            async with AsyncSqliteSaver.from_conn_string(database) as checkpointer:
                graph = goal_graph.build_goal_graph(checkpointer)
                result = await goal_graph.run_goal(
                    graph,
                    "finish",
                    "async-run-goal",
                    runtime,
                    retries=0,
                )

        self.assertEqual(result["status"], "achieved")
        self.assertEqual(model.roles, ["leader", "follower"])


if __name__ == "__main__":
    unittest.main()
