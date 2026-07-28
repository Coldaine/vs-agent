"""Behavioral tests for the official Codex SDK client boundary."""

from __future__ import annotations

import asyncio
import json
import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "spine"))

import codex_sdk_client  # noqa: E402


class FakeTurn:
    def __init__(
        self,
        final_response: str = '{"direction":"HOLD"}',
        turn_id: str = "turn-1",
        usage: dict | None = None,
    ) -> None:
        self.final_response = final_response
        self.id = turn_id
        self.usage = usage


class FakeThread:
    def __init__(self, thread_id: str, turn: FakeTurn | None = None) -> None:
        self.id = thread_id
        self.turn = turn or FakeTurn()
        self.run_calls: list[tuple[str, dict]] = []

    async def run(self, prompt: str, **kwargs):
        self.run_calls.append((prompt, kwargs))
        return self.turn


class FakeSDK:
    def __init__(self, account: dict, thread: FakeThread) -> None:
        self.account_value = account
        self.thread = thread
        self.enter_count = 0
        self.exit_count = 0
        self.started: list[dict] = []
        self.resumed: list[tuple[str, dict]] = []

    async def __aenter__(self):
        self.enter_count += 1
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        self.exit_count += 1

    async def account(self):
        return self.account_value

    async def thread_start(self, **kwargs):
        self.started.append(kwargs)
        return self.thread

    async def thread_resume(self, thread_id: str, **kwargs):
        self.resumed.append((thread_id, kwargs))
        return self.thread


class BlockingFakeSDK(FakeSDK):
    def __init__(
        self,
        account: dict,
        thread: FakeThread,
        entered: asyncio.Event,
        release: asyncio.Event,
    ) -> None:
        super().__init__(account, thread)
        self.entered = entered
        self.release = release

    async def __aenter__(self):
        self.enter_count += 1
        self.entered.set()
        await self.release.wait()
        return self


class CodexAgentClientTests(unittest.IsolatedAsyncioTestCase):
    def _client(self, sdk: FakeSDK, image_factory=lambda path: ("image", path)):
        self.sandbox = object()
        self.approval_mode = object()
        return codex_sdk_client.CodexAgentClient(
            sdk_factory=lambda: sdk,
            image_factory=image_factory,
            sandbox=self.sandbox,
            approval_mode=self.approval_mode,
        )

    async def test_start_enters_one_chatgpt_managed_sdk_client(self) -> None:
        sdk = FakeSDK({"account": {"type": "chatgpt"}}, FakeThread("thread-1"))
        client = self._client(sdk)

        await client.start()
        await client.start()

        self.assertEqual(sdk.enter_count, 1)

    async def test_concurrent_starts_enter_and_close_one_sdk_context(self) -> None:
        release = asyncio.Event()
        first = BlockingFakeSDK(
            {"account": {"type": "chatgpt"}},
            FakeThread("first-thread"),
            asyncio.Event(),
            release,
        )
        second = BlockingFakeSDK(
            {"account": {"type": "chatgpt"}},
            FakeThread("second-thread"),
            asyncio.Event(),
            release,
        )
        sdk_factories = iter((first, second))
        client = codex_sdk_client.CodexAgentClient(
            sdk_factory=lambda: next(sdk_factories)
        )

        first_start = asyncio.create_task(client.start())
        await asyncio.wait_for(first.entered.wait(), timeout=1)
        second_start = asyncio.create_task(client.start())
        await asyncio.sleep(0)
        release.set()
        await asyncio.gather(first_start, second_start)
        await client.close()

        self.assertEqual(first.enter_count, 1)
        self.assertEqual(second.enter_count, 0)
        self.assertEqual(first.exit_count, 1)
        self.assertEqual(second.exit_count, 0)

    async def test_start_rejects_non_chatgpt_managed_authentication(self) -> None:
        sdk = FakeSDK({"account": {"type": "apiKey"}}, FakeThread("thread-1"))

        with self.assertRaisesRegex(RuntimeError, "ChatGPT-managed"):
            await self._client(sdk).start()

        self.assertEqual(sdk.exit_count, 1)

    async def test_invoke_starts_a_role_thread_with_restricted_sdk_options(self) -> None:
        thread = FakeThread("leader-thread", FakeTurn('{"intent":"hold"}', usage={"total_tokens": 12}))
        sdk = FakeSDK({"account": {"type": "chatgpt"}}, thread)
        client = self._client(sdk)

        invocation = await client.invoke(
            "leader", "Return a decision.", {"type": "object"}
        )

        self.assertEqual(invocation.payload, {"intent": "hold"})
        self.assertEqual(invocation.thread_id, "leader-thread")
        self.assertEqual(invocation.turn_id, "turn-1")
        self.assertEqual(invocation.usage, {"total_tokens": 12})
        self.assertEqual(len(sdk.started), 1)
        self.assertEqual(sdk.started[0]["sandbox"], self.sandbox)
        self.assertEqual(sdk.started[0]["approval_mode"], self.approval_mode)
        self.assertEqual(
            sdk.started[0]["config"],
            {"web_search": "disabled", "features": {"shell_tool": False}},
        )
        self.assertEqual(thread.run_calls[0][0], "Return a decision.")
        self.assertEqual(thread.run_calls[0][1]["output_schema"], {"type": "object"})

    async def test_invoke_resumes_the_supplied_thread_id(self) -> None:
        thread = FakeThread("continued-thread")
        sdk = FakeSDK({"account": {"type": "chatgpt"}}, thread)

        invocation = await self._client(sdk).invoke(
            "follower", "Inspect this.", {"type": "object"}, thread_id="prior-thread"
        )

        self.assertEqual(
            sdk.resumed,
            [("prior-thread", {
                "approval_mode": self.approval_mode,
                "sandbox": self.sandbox,
                "config": {"web_search": "disabled", "features": {"shell_tool": False}},
            })],
        )
        self.assertEqual(sdk.started, [])
        self.assertEqual(invocation.thread_id, "continued-thread")

    async def test_invoke_rejects_resuming_a_thread_owned_by_another_role(self) -> None:
        thread = FakeThread("shared-thread")
        sdk = FakeSDK({"account": {"type": "chatgpt"}}, thread)
        client = self._client(sdk)

        await client.invoke("leader", "Lead.", {"type": "object"})

        with self.assertRaisesRegex(RuntimeError, "different role"):
            await client.invoke(
                "follower", "Follow.", {"type": "object"}, thread_id="shared-thread"
            )

        self.assertEqual(sdk.resumed, [])

    async def test_invoke_passes_an_image_as_a_local_sdk_input(self) -> None:
        thread = FakeThread("follower-thread")
        sdk = FakeSDK({"account": {"type": "chatgpt"}}, thread)
        seen_paths: list[str] = []

        def image_factory(path: str):
            seen_paths.append(path)
            return ("local-image", path)

        await self._client(sdk, image_factory).invoke(
            "follower", "Inspect frame.", {"type": "object"}, image_path=Path("frame.jpg")
        )

        self.assertEqual(seen_paths, ["frame.jpg"])
        self.assertEqual(
            thread.run_calls[0][0],
            ["Inspect frame.", ("local-image", "frame.jpg")],
        )

    async def test_invoke_rejects_an_invalid_json_final_response(self) -> None:
        thread = FakeThread("leader-thread", FakeTurn("not json"))
        sdk = FakeSDK({"account": {"type": "chatgpt"}}, thread)

        with self.assertRaisesRegex(RuntimeError, "invalid JSON"):
            await self._client(sdk).invoke("leader", "Return JSON.", {"type": "object"})

    async def test_invoke_rejects_a_json_object_that_violates_its_schema(self) -> None:
        thread = FakeThread("leader-thread", FakeTurn('{"direction":"SIDEWAYS"}'))
        sdk = FakeSDK({"account": {"type": "chatgpt"}}, thread)
        schema = {
            "type": "object",
            "properties": {"direction": {"enum": ["HOLD"]}},
            "required": ["direction"],
            "additionalProperties": False,
        }

        with self.assertRaisesRegex(RuntimeError, "schema"):
            await self._client(sdk).invoke("leader", "Return JSON.", schema)

    async def test_close_exits_the_sdk_context_once(self) -> None:
        sdk = FakeSDK({"account": {"type": "chatgpt"}}, FakeThread("thread-1"))
        client = self._client(sdk)
        await client.start()

        await client.close()
        await client.close()

        self.assertEqual(sdk.exit_count, 1)


if __name__ == "__main__":
    unittest.main()
