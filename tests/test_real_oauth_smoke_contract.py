"""Machine-readable evidence contract for the real OAuth graph smoke."""

from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "spine"))

from smoke_oauth_graph import run_smoke, validate_smoke_result  # noqa: E402


def valid_smoke_result() -> dict:
    return {
        "contract_version": 1,
        "status": "achieved",
        "account": {"type": "chatgpt", "plan_type": "pro"},
        "model": {
            "configured": "gpt-5.6-luna",
            "catalog_available": True,
            "catalog_input_modalities": ["text", "image"],
            "turn_result_echoed_model": False,
        },
        "langgraph": {
            "parent_thread_id": "oauth-smoke",
            "child_graphs": ["leader_agent", "follower_agent"],
        },
        "roles": {
            "leader": {
                "graph_name": "leader_agent",
                "codex_thread_id": "leader-thread",
                "turn_id": "leader-turn",
                "decision": {
                    "intent": "survive",
                    "option": None,
                    "reason": "safe",
                },
                "schema_valid": True,
            },
            "follower": {
                "graph_name": "follower_agent",
                "codex_thread_id": "follower-thread",
                "turn_id": "follower-turn",
                "decision": {
                    "direction": "HOLD",
                    "confidence": 1.0,
                    "reason": "safe",
                },
                "schema_valid": True,
            },
        },
        "image": {
            "role": "leader",
            "attached": True,
            "source": "status/g0_capture.jpg",
            "schema_valid": True,
        },
        "game_input": {"emitted": False},
    }


class RealOauthSmokeContractTests(unittest.TestCase):
    def test_accepts_complete_chatgpt_graph_and_image_evidence(self) -> None:
        result = valid_smoke_result()

        self.assertIs(validate_smoke_result(result), result)

    def test_rejects_missing_auth_roles_threads_or_schema_valid_payloads(self) -> None:
        mutations = {
            "missing account type": lambda value: value["account"].pop("type"),
            "non ChatGPT account": lambda value: value["account"].update(type="apiKey"),
            "missing follower role": lambda value: value["roles"].pop("follower"),
            "missing role thread": lambda value: value["roles"]["leader"].pop(
                "codex_thread_id"
            ),
            "wrong role graph": lambda value: value["roles"]["leader"].update(
                graph_name="follower_agent"
            ),
            "missing turn id": lambda value: value["roles"]["leader"].pop(
                "turn_id"
            ),
            "duplicate role thread": lambda value: value["roles"]["follower"].update(
                codex_thread_id="leader-thread"
            ),
            "invalid leader decision": lambda value: value["roles"]["leader"].update(
                decision={"intent": "survive"}
            ),
            "invalid follower decision": lambda value: value["roles"]["follower"].update(
                decision={"direction": "SIDEWAYS", "confidence": 1.0, "reason": "bad"}
            ),
            "missing child graph": lambda value: value["langgraph"].update(
                child_graphs=["leader_agent"]
            ),
            "wrong configured model": lambda value: value["model"].update(
                configured="gpt-5.5"
            ),
            "catalog lacks image input": lambda value: value["model"].update(
                catalog_input_modalities=["text"]
            ),
            "image not attached": lambda value: value["image"].update(attached=False),
            "image role is unknown": lambda value: value["image"].update(role="reviewer"),
            "game input emitted": lambda value: value["game_input"].update(emitted=True),
        }

        for label, mutate in mutations.items():
            with self.subTest(label=label):
                result = copy.deepcopy(valid_smoke_result())
                mutate(result)
                with self.assertRaises((ValueError, RuntimeError)):
                    validate_smoke_result(result)


class FakeTurn:
    def __init__(self, final_response: str, turn_id: str) -> None:
        self.final_response = final_response
        self.id = turn_id
        self.usage = None


class FakeThread:
    def __init__(self, thread_id: str, response: dict) -> None:
        self.id = thread_id
        self.response = response
        self.inputs = []

    async def run(self, input_value, **kwargs):
        self.inputs.append(input_value)
        return FakeTurn(json.dumps(self.response), f"{self.id}-turn")


class FakePublicSdk:
    def __init__(self) -> None:
        self.started = []
        self.exited = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        self.exited = True

    async def account(self):
        return {"account": {"type": "chatgpt", "plan_type": "pro"}}

    async def models(self, *, include_hidden=False):
        return SimpleNamespace(
            data=[
                SimpleNamespace(
                    id="gpt-5.6-luna",
                    model="gpt-5.6-luna",
                    hidden=False,
                    input_modalities=["text", "image"],
                )
            ]
        )

    async def thread_start(self, **kwargs):
        self.started.append(kwargs)
        if len(self.started) == 1:
            return FakeThread(
                "leader-thread",
                {"intent": "survive", "option": None, "reason": "safe"},
            )
        return FakeThread(
            "follower-thread",
            {"direction": "HOLD", "confidence": 1.0, "reason": "safe"},
        )

    async def thread_resume(self, thread_id, **kwargs):
        raise AssertionError("fresh smoke must not resume a thread")


class RealOauthSmokeProducerTests(unittest.IsolatedAsyncioTestCase):
    async def test_graph_smoke_produces_complete_public_evidence_contract(self) -> None:
        sdk = FakePublicSdk()
        image_path = Path(__file__).resolve().parents[1] / "status" / "g0_capture.jpg"

        result = await run_smoke(
            sdk_factory=lambda: sdk,
            image_path=image_path,
        )

        self.assertEqual(result["status"], "achieved")
        self.assertEqual(result["account"], {"type": "chatgpt", "plan_type": "pro"})
        self.assertEqual(result["model"]["configured"], "gpt-5.6-luna")
        self.assertTrue(result["model"]["catalog_available"])
        self.assertEqual(
            result["langgraph"]["child_graphs"],
            ["leader_agent", "follower_agent"],
        )
        self.assertNotEqual(
            result["roles"]["leader"]["codex_thread_id"],
            result["roles"]["follower"]["codex_thread_id"],
        )
        self.assertTrue(result["image"]["attached"])
        self.assertFalse(result["game_input"]["emitted"])
        self.assertTrue(sdk.exited)
        self.assertEqual([call["model"] for call in sdk.started], ["gpt-5.6-luna"] * 2)


if __name__ == "__main__":
    unittest.main()
