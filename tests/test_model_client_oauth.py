"""Compatibility model helpers must also use ChatGPT OAuth, never HTTP APIs."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "spine"))

import model_client  # noqa: E402
from codex_sdk_client import CodexInvocation  # noqa: E402


class FakeCodexClient:
    def __init__(self, responses: list[dict]) -> None:
        self.responses = list(responses)
        self.calls: list[tuple] = []
        self.events: list[str] = []

    async def start(self) -> None:
        self.events.append("start")

    async def close(self) -> None:
        self.events.append("close")

    async def invoke(self, role, prompt, schema, image_path=None, thread_id=None):
        self.calls.append((role, prompt, schema, image_path))
        return CodexInvocation(
            self.responses.pop(0), f"{role}-thread", f"{role}-turn", None
        )


class ModelClientOAuthTests(unittest.TestCase):
    def tearDown(self) -> None:
        model_client.set_client_factory_for_testing(None)

    def test_follower_uses_oauth_follower_with_image_attachment(self) -> None:
        runner = FakeCodexClient([
            {"direction": "SW", "speed": 0.6, "reason": "escape"}
        ])
        model_client.set_client_factory_for_testing(lambda: runner)
        with tempfile.NamedTemporaryFile(suffix=".jpg") as frame:
            direction, speed = model_client.call_follower(
                "State {{STATE_JSON}} brief {{STRATEGY_BRIEF}}",
                {"hp": 12},
                frame.name,
                "survive",
            )

        self.assertEqual((direction, speed), ("SW", 0.6))
        self.assertEqual(runner.calls[0][0], "follower")
        self.assertEqual(runner.calls[0][3], Path(frame.name))
        self.assertEqual(runner.events, ["start", "close"])

    def test_leader_uses_oauth_leader(self) -> None:
        runner = FakeCodexClient([
            {"pick": 2, "why": "damage", "brief_update": "keep moving"}
        ])
        model_client.set_client_factory_for_testing(lambda: runner)

        result = model_client.call_leader(
            "Choose.", None, ["A", "B", "C"], "old brief"
        )

        self.assertEqual(result["pick"], 2)
        self.assertEqual(runner.calls[0][0], "leader")

    def test_compatibility_helpers_fail_closed_when_api_key_is_inherited(self) -> None:
        runner = FakeCodexClient([
            {"pick": 1, "why": "", "brief_update": ""}
        ])
        model_client.set_client_factory_for_testing(lambda: runner)

        with mock.patch.dict(os.environ, {"OPENAI_API_KEY": "forbidden"}, clear=False):
            with self.assertRaisesRegex(RuntimeError, "ChatGPT Pro OAuth only"):
                model_client.call_leader("Choose.", None, ["A"], "")

        self.assertEqual(runner.calls, [])


class ModelClientAsyncBoundaryTests(unittest.IsolatedAsyncioTestCase):
    def tearDown(self) -> None:
        model_client.set_client_factory_for_testing(None)

    async def test_async_helper_uses_official_client_without_nested_loop(self) -> None:
        client = FakeCodexClient([
            {"pick": 1, "why": "safe", "brief_update": "hold course"}
        ])
        model_client.set_client_factory_for_testing(lambda: client)

        result = await model_client.acall_leader("Choose.", None, ["A"], "")

        self.assertEqual(result["pick"], 1)
        self.assertEqual(client.events, ["start", "close"])

    async def test_sync_helper_rejects_use_inside_running_event_loop(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "await acall_leader"):
            model_client.call_leader("Choose.", None, ["A"], "")


if __name__ == "__main__":
    unittest.main()
