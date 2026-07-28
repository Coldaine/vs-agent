"""Behavioral tests for the durable LangGraph goal runtime."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "spine"))

from langgraph.checkpoint.memory import InMemorySaver  # noqa: E402
from langgraph.checkpoint.sqlite import SqliteSaver  # noqa: E402

import goal_graph  # noqa: E402


class ScriptedModel:
    def __init__(self) -> None:
        self.roles: list[str] = []
        self.image_paths: list[tuple[str, object]] = []

    def invoke(self, role: str, prompt: str, schema: dict, image_path=None) -> dict:
        self.roles.append(role)
        self.image_paths.append((role, image_path))
        if role == "leader":
            if "LEVEL_UP" in prompt:
                return {"intent": "choose upgrade", "option": 2, "reason": "damage"}
            return {"intent": "farm open ground", "option": None, "reason": "safe growth"}
        return {"direction": "NE", "confidence": 0.8, "reason": "open lane"}


class ScriptedTools:
    def __init__(self, observations: list[dict], evaluation: dict | None = None) -> None:
        self.observations = list(observations)
        self.evaluation = evaluation or {
            "status": "achieved",
            "reason": "target proven",
            "evidence": ["outcome.json"],
        }
        self.calls: list[object] = []

    def prepare(self) -> dict:
        self.calls.append("prepare")
        return {"run_id": "run-test", "verified": True}

    def observe(self) -> dict:
        self.calls.append("observe")
        return self.observations.pop(0)

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

    def neutralize(self) -> None:
        self.calls.append("neutralize")


class GoalGraphTests(unittest.TestCase):
    def test_play_cycle_uses_leader_then_follower_and_ends_on_evidence(self) -> None:
        model = ScriptedModel()
        tools = ScriptedTools([
            {"screen_type": "PLAY", "summary": "clear northeast", "image_path": "frame.jpg"},
            {"screen_type": "RUN_END", "summary": "run ended"},
        ])
        times = iter([10.0, 10.321])
        graph = goal_graph.build_goal_graph(
            model, tools, InMemorySaver(), clock=lambda: next(times)
        )

        result = graph.invoke(
            goal_graph.initial_state("survive at least 9 minutes", retries=1),
            {"configurable": {"thread_id": "play-cycle"}, "recursion_limit": 30},
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

    def test_level_up_routes_to_leader_without_calling_follower(self) -> None:
        model = ScriptedModel()
        tools = ScriptedTools([
            {"screen_type": "LEVEL_UP", "summary": "three options"},
            {"screen_type": "RUN_END", "summary": "run ended"},
        ])
        graph = goal_graph.build_goal_graph(model, tools, InMemorySaver())

        result = graph.invoke(
            goal_graph.initial_state("complete one run", retries=0),
            {"configurable": {"thread_id": "level-up"}, "recursion_limit": 30},
        )

        self.assertEqual(result["status"], "achieved")
        self.assertEqual(model.roles, ["leader"])
        self.assertIn(("select_level_up", 2), tools.calls)

    def test_safety_fault_neutralizes_and_blocks_without_model_call(self) -> None:
        model = ScriptedModel()
        tools = ScriptedTools([{"screen_type": "SAFETY_FAULT", "summary": "capture lost"}])
        graph = goal_graph.build_goal_graph(model, tools, InMemorySaver())

        result = graph.invoke(
            goal_graph.initial_state("complete one run", retries=1),
            {"configurable": {"thread_id": "fault"}},
        )

        self.assertEqual(result["status"], "blocked")
        self.assertIn("capture lost", result["reason"])
        self.assertEqual(model.roles, [])
        self.assertEqual(tools.calls[-1], "neutralize")

    def test_rejected_follower_direction_neutralizes_and_blocks(self) -> None:
        class InvalidFollower(ScriptedModel):
            def invoke(self, role: str, prompt: str, schema: dict, image_path=None) -> dict:
                if role == "follower":
                    self.roles.append(role)
                    return {"direction": "TELEPORT", "confidence": 1.0, "reason": "invalid"}
                return super().invoke(role, prompt, schema, image_path)

        model = InvalidFollower()
        tools = ScriptedTools([{"screen_type": "PLAY", "summary": "open"}])
        graph = goal_graph.build_goal_graph(model, tools, InMemorySaver())

        result = graph.invoke(
            goal_graph.initial_state("complete one run", retries=0),
            {"configurable": {"thread_id": "invalid-direction"}},
        )

        self.assertEqual(result["status"], "blocked")
        self.assertIn("TELEPORT", result["reason"])
        self.assertEqual(tools.calls[-1], "neutralize")

    def test_not_met_evaluation_retries_only_within_budget(self) -> None:
        model = ScriptedModel()
        tools = ScriptedTools(
            [
                {"screen_type": "RUN_END", "summary": "first run"},
                {"screen_type": "RUN_END", "summary": "second run"},
            ],
            evaluation={"status": "not_met", "reason": "too short", "evidence": []},
        )
        graph = goal_graph.build_goal_graph(model, tools, InMemorySaver())

        result = graph.invoke(
            goal_graph.initial_state("survive 9 minutes", retries=1),
            {"configurable": {"thread_id": "retry-budget"}, "recursion_limit": 30},
        )

        self.assertEqual(result["status"], "not_met")
        self.assertEqual(result["retries_left"], 0)
        self.assertEqual(tools.calls.count("prepare"), 2)

    def test_checkpoint_resume_continues_after_observation_without_repreparing(self) -> None:
        model = ScriptedModel()
        tools = ScriptedTools([
            {"screen_type": "PLAY", "summary": "safe"},
            {"screen_type": "RUN_END", "summary": "done"},
        ])
        graph = goal_graph.build_goal_graph(
            model, tools, InMemorySaver(), pause_after_observe=True
        )
        config = {"configurable": {"thread_id": "resume"}, "recursion_limit": 30}

        paused = graph.invoke(goal_graph.initial_state("finish", retries=0), config)
        self.assertEqual(paused["phase"], "observed")
        self.assertEqual(tools.calls.count("prepare"), 1)

        resumed = graph.invoke(None, config)

        self.assertEqual(resumed["phase"], "observed")
        self.assertEqual(tools.calls.count("prepare"), 1)
        self.assertEqual(model.roles, ["leader", "follower"])

    def test_sqlite_checkpoint_resumes_after_graph_is_rebuilt(self) -> None:
        model = ScriptedModel()
        tools = ScriptedTools([
            {"screen_type": "PLAY", "summary": "safe"},
            {"screen_type": "RUN_END", "summary": "done"},
        ])
        config = {"configurable": {"thread_id": "sqlite-resume"}, "recursion_limit": 30}
        with tempfile.TemporaryDirectory() as root:
            database = str(Path(root, "goals.sqlite3"))
            with SqliteSaver.from_conn_string(database) as checkpointer:
                first_graph = goal_graph.build_goal_graph(
                    model, tools, checkpointer, pause_after_observe=True
                )
                paused = first_graph.invoke(
                    goal_graph.initial_state("finish", retries=0), config
                )
                self.assertEqual(paused["phase"], "observed")

            with SqliteSaver.from_conn_string(database) as checkpointer:
                rebuilt_graph = goal_graph.build_goal_graph(
                    model, tools, checkpointer, pause_after_observe=True
                )
                resumed = rebuilt_graph.invoke(None, config)

        self.assertEqual(resumed["phase"], "observed")
        self.assertEqual(tools.calls.count("prepare"), 1)
        self.assertEqual(model.roles, ["leader", "follower"])


if __name__ == "__main__":
    unittest.main()
