"""CLI contract tests for the LangGraph goal entry point."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "spine"))

import run  # noqa: E402
from codex_sdk_client import CodexInvocation  # noqa: E402
import goal_graph  # noqa: E402


class RecordingCodexClient:
    instances = []

    def __init__(self, *, thread_bindings=None) -> None:
        self.events = []
        self._thread_bindings = dict(thread_bindings or {})
        type(self).instances.append(self)

    @property
    def thread_bindings(self):
        return dict(self._thread_bindings)

    async def start(self) -> None:
        self.events.append("start")

    async def close(self) -> None:
        self.events.append("close")

    async def invoke(self, role, prompt, schema, image_path=None, thread_id=None):
        self.events.append(("invoke", role, thread_id))
        assigned = thread_id or f"{role}-sdk-thread"
        self._thread_bindings[role] = assigned
        payload = (
            {"intent": "continue", "option": None, "reason": "safe"}
            if role == "leader"
            else {"direction": "HOLD", "confidence": 1.0, "reason": "safe"}
        )
        return CodexInvocation(payload, assigned, f"{role}-turn", None)


class RecordingTools:
    writer = None  # match real SpineGameTools

    def __init__(self, *args, fail_model=False, **kwargs) -> None:
        self.events = []
        self.observations = [
            {"screen_type": "PLAY", "summary": "synthetic"},
            {"screen_type": "RUN_END", "summary": "complete"},
        ]

    def prepare(self):
        return {"verified": True, "run_id": "runtime-test", "entry_only": False}

    def observe(self):
        return self.observations.pop(0)

    def menu_action(self, action, click=None):
        raise AssertionError("not a menu test")

    def mark_in_game(self):
        raise AssertionError("not an entry test")

    def submit_direction(self, direction, latency_ms):
        return True

    def control_window(self, seconds):
        return {"safe": True, "evidence": ["controlled"]}

    def select_level_up(self, option):
        raise AssertionError("not a level-up test")

    def evaluate(self, goal, run_id):
        return {"status": "achieved", "reason": "complete", "evidence": ["done"]}

    def evaluate_entry(self, run_id):
        raise AssertionError("not an entry test")

    def neutralize(self):
        self.events.append("neutralize")

    def close(self):
        self.events.append("close-tools")

    def restore_checkpoint(self, state):
        self.events.append("restore-checkpoint")
        return True


class FailingCodexClient(RecordingCodexClient):
    async def invoke(self, role, prompt, schema, image_path=None, thread_id=None):
        self.events.append(("invoke", role, thread_id))
        raise RuntimeError("model failed")


class GoalCliTests(unittest.TestCase):
    def test_goal_is_the_default_model_driven_runtime(self) -> None:
        args = run.build_parser().parse_args([
            "--goal",
            "survive nine minutes under fixed conditions",
            "--thread-id",
            "goal-9",
            "--retries",
            "2",
        ])

        self.assertEqual(args.goal, "survive nine minutes under fixed conditions")
        self.assertEqual(args.thread_id, "goal-9")
        self.assertEqual(args.retries, 2)
        self.assertFalse(hasattr(args, "legacy_api"))

    def test_default_goal_names_the_deterministic_evidence_target(self) -> None:
        args = run.build_parser().parse_args([])

        self.assertIn("540 seconds", args.goal)
        self.assertIn("fixed", args.goal.lower())

    def test_attach_flag_is_available_for_live_recovery(self) -> None:
        args = run.build_parser().parse_args(["--attach"])

        self.assertTrue(args.attach)

    def test_entry_only_flag_is_available_for_vision_menu_proof(self) -> None:
        args = run.build_parser().parse_args(["--entry-only"])

        self.assertTrue(args.entry_only)


class GoalRuntimeTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        RecordingCodexClient.instances = []
        FailingCodexClient.instances = []

    async def test_one_sdk_client_spans_both_roles_and_closes_after_success(self) -> None:
        tools = RecordingTools()
        with tempfile.TemporaryDirectory() as root, mock.patch.object(
            run, "IOAdapter", return_value=object()
        ), mock.patch.object(run, "Controller", return_value=object()), mock.patch.object(
            run, "SpineGameTools", return_value=tools
        ), mock.patch.object(run, "CodexAgentClient", RecordingCodexClient):
            result = await run.run_langgraph_goal(
                "finish the synthetic run",
                thread_id="runtime-success",
                retries=0,
                checkpoint_path=str(Path(root, "checkpoint.sqlite3")),
                config_path=str(Path(__file__).parents[1] / "spine" / "config.yaml"),
            )

        self.assertEqual(result["status"], "achieved")
        self.assertEqual(len(RecordingCodexClient.instances), 1)
        client = RecordingCodexClient.instances[0]
        self.assertEqual(client.events[0], "start")
        self.assertEqual(
            [event[1] for event in client.events if isinstance(event, tuple)],
            ["leader", "follower"],
        )
        self.assertEqual(client.events[-1], "close")
        self.assertIn("neutralize", tools.events)
        self.assertEqual(tools.events[-1], "close-tools")


class GoalResumeAndFailureTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        RecordingCodexClient.instances = []
        FailingCodexClient.instances = []

    async def test_resume_hydrates_only_checkpointed_role_thread_bindings(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            checkpoint = str(Path(root, "checkpoint.sqlite3"))
            first_tools = RecordingTools()
            with mock.patch.object(run, "IOAdapter", return_value=object()), mock.patch.object(
                run, "Controller", return_value=object()
            ), mock.patch.object(
                run, "SpineGameTools", return_value=first_tools
            ), mock.patch.object(
                run, "CodexAgentClient", RecordingCodexClient
            ), mock.patch.object(
                run,
                "build_goal_graph",
                side_effect=lambda checkpointer: goal_graph.build_goal_graph(
                    checkpointer, pause_after_leader=True
                ),
            ):
                paused = await run.run_langgraph_goal(
                    "finish the synthetic run",
                    thread_id="runtime-resume",
                    retries=0,
                    checkpoint_path=checkpoint,
                    config_path=str(Path(__file__).parents[1] / "spine" / "config.yaml"),
                )

            self.assertEqual(paused["leader_codex_thread_id"], "leader-sdk-thread")
            second_tools = RecordingTools()
            with mock.patch.object(run, "IOAdapter", return_value=object()), mock.patch.object(
                run, "Controller", return_value=object()
            ), mock.patch.object(
                run, "SpineGameTools", return_value=second_tools
            ), mock.patch.object(run, "CodexAgentClient", RecordingCodexClient):
                resumed = await run.run_langgraph_goal(
                    "ignored on resume",
                    thread_id="runtime-resume",
                    retries=99,
                    checkpoint_path=checkpoint,
                    config_path=str(Path(__file__).parents[1] / "spine" / "config.yaml"),
                )

        self.assertEqual(resumed["status"], "achieved")
        self.assertEqual(len(RecordingCodexClient.instances), 2)
        resumed_client = RecordingCodexClient.instances[1]
        self.assertEqual(
            resumed_client.events[1], ("invoke", "follower", None)
        )
        self.assertEqual(
            resumed_client.thread_bindings,
            {"leader": "leader-sdk-thread", "follower": "follower-sdk-thread"},
        )
        self.assertIn("restore-checkpoint", second_tools.events)

    async def test_model_failure_still_neutralizes_tools_and_closes_sdk(self) -> None:
        tools = RecordingTools()
        with tempfile.TemporaryDirectory() as root, mock.patch.object(
            run, "IOAdapter", return_value=object()
        ), mock.patch.object(run, "Controller", return_value=object()), mock.patch.object(
            run, "SpineGameTools", return_value=tools
        ), mock.patch.object(run, "CodexAgentClient", FailingCodexClient):
            with self.assertRaisesRegex(RuntimeError, "model failed"):
                await run.run_langgraph_goal(
                    "fail safely",
                    thread_id="runtime-failure",
                    retries=0,
                    checkpoint_path=str(Path(root, "checkpoint.sqlite3")),
                    config_path=str(Path(__file__).parents[1] / "spine" / "config.yaml"),
                )

        self.assertEqual(len(FailingCodexClient.instances), 1)
        self.assertEqual(FailingCodexClient.instances[0].events[-1], "close")
        self.assertIn("neutralize", tools.events)
        self.assertEqual(tools.events[-1], "close-tools")


if __name__ == "__main__":
    unittest.main()
