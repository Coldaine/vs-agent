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


class FakeOAuthRunner:
    def __init__(self, responses: list[dict]) -> None:
        self.responses = list(responses)
        self.calls: list[tuple] = []

    def invoke(self, role, prompt, schema, image_path=None):
        self.calls.append((role, prompt, schema, image_path))
        return self.responses.pop(0)


class ModelClientOAuthTests(unittest.TestCase):
    def tearDown(self) -> None:
        model_client.set_runner_for_testing(None)

    def test_pilot_uses_oauth_follower_with_image_attachment(self) -> None:
        runner = FakeOAuthRunner([
            {"direction": "SW", "speed": 0.6, "reason": "escape"}
        ])
        model_client.set_runner_for_testing(runner)
        with tempfile.NamedTemporaryFile(suffix=".jpg") as frame:
            direction, speed = model_client.call_pilot(
                "State {{STATE_JSON}} brief {{STRATEGY_BRIEF}}",
                {"hp": 12},
                frame.name,
                "survive",
            )

        self.assertEqual((direction, speed), ("SW", 0.6))
        self.assertEqual(runner.calls[0][0], "follower")
        self.assertEqual(runner.calls[0][3], Path(frame.name))

    def test_planner_uses_oauth_leader(self) -> None:
        runner = FakeOAuthRunner([
            {"pick": 2, "why": "damage", "brief_update": "keep moving"}
        ])
        model_client.set_runner_for_testing(runner)

        result = model_client.call_planner(
            "Choose.", None, ["A", "B", "C"], "old brief"
        )

        self.assertEqual(result["pick"], 2)
        self.assertEqual(runner.calls[0][0], "leader")

    def test_compatibility_helpers_fail_closed_when_api_key_is_inherited(self) -> None:
        runner = FakeOAuthRunner([
            {"pick": 1, "why": "", "brief_update": ""}
        ])
        model_client.set_runner_for_testing(runner)

        with mock.patch.dict(os.environ, {"OPENAI_API_KEY": "forbidden"}, clear=False):
            with self.assertRaisesRegex(RuntimeError, "ChatGPT Pro OAuth only"):
                model_client.call_planner("Choose.", None, ["A"], "")

        self.assertEqual(runner.calls, [])


if __name__ == "__main__":
    unittest.main()
