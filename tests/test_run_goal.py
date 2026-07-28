"""CLI contract tests for the LangGraph goal entry point."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "spine"))

import run  # noqa: E402


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


if __name__ == "__main__":
    unittest.main()
