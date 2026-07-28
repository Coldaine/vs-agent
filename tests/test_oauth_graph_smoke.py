"""The reproducible OAuth graph smoke must exercise both model roles."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "spine"))

import smoke_oauth_graph  # noqa: E402


class FakeRunner:
    def __init__(self) -> None:
        self.roles: list[str] = []

    def invoke(self, role, prompt, schema, image_path=None):
        self.roles.append(role)
        if role == "leader":
            return {"intent": "continue safely", "option": None, "reason": "smoke"}
        return {"direction": "HOLD", "confidence": 1.0, "reason": "smoke"}


class OAuthGraphSmokeTests(unittest.TestCase):
    def test_smoke_reaches_evidence_evaluation_through_leader_and_follower(self) -> None:
        runner = FakeRunner()

        result = smoke_oauth_graph.run_smoke(runner)

        self.assertEqual(result["status"], "achieved")
        self.assertEqual(runner.roles, ["leader", "follower"])
        self.assertEqual(result["evidence"], ["smoke-control", "smoke-outcome"])


if __name__ == "__main__":
    unittest.main()
