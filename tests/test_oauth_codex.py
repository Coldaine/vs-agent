"""Behavioral tests for the ChatGPT Pro OAuth-only Codex adapter."""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "spine"))

import oauth_codex  # noqa: E402


class RecordingExecutor:
    def __init__(self, response: dict | None = None, login_text: str = "Logged in using ChatGPT") -> None:
        self.response = response or {"direction": "NE", "confidence": 0.75, "reason": "open lane"}
        self.login_text = login_text
        self.calls: list[tuple[list[str], dict]] = []

    def __call__(self, command: list[str], **kwargs) -> subprocess.CompletedProcess[str]:
        self.calls.append((command, kwargs))
        if command[-2:] == ["login", "status"]:
            return subprocess.CompletedProcess(command, 0, self.login_text, "")
        output_path = Path(command[command.index("--output-last-message") + 1])
        output_path.write_text(json.dumps(self.response), encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, "", "")


class OAuthEnvironmentTests(unittest.TestCase):
    def test_rejects_every_api_key_that_could_silently_change_the_auth_path(self) -> None:
        for name in ("OPENAI_API_KEY", "OPENROUTER_API_KEY", "DEEPSEEK_API_KEY"):
            with self.subTest(name=name):
                with self.assertRaisesRegex(RuntimeError, "ChatGPT Pro OAuth only"):
                    oauth_codex.assert_oauth_only_environment({name: "must-not-be-used"})

    def test_accepts_environment_without_api_keys(self) -> None:
        oauth_codex.assert_oauth_only_environment({"CODEX_HOME": "C:/oauth-owned-by-codex"})


class CodexOAuthRunnerTests(unittest.TestCase):
    def test_refuses_non_chatgpt_login(self) -> None:
        executor = RecordingExecutor(login_text="Logged in using an API key")
        runner = oauth_codex.CodexOAuthRunner(executor=executor, environ={})

        with self.assertRaisesRegex(RuntimeError, "not ChatGPT OAuth"):
            runner.check_login()

    def test_leader_and_follower_use_luna_through_oauth_safe_codex_exec(self) -> None:
        schema = {
            "type": "object",
            "properties": {"direction": {"type": "string"}},
            "required": ["direction"],
            "additionalProperties": False,
        }
        executor = RecordingExecutor()
        runner = oauth_codex.CodexOAuthRunner(executor=executor, environ={})

        for role in ("leader", "follower"):
            result = runner.invoke(role, f"Return a proposal for {role}.", schema)
            self.assertEqual(result["direction"], "NE")

        exec_calls = [call for call in executor.calls if len(call[0]) > 1 and call[0][1] == "exec"]
        self.assertEqual(len(exec_calls), 2)
        for command, kwargs in exec_calls:
            self.assertIn("--ignore-user-config", command)
            self.assertIn("--ignore-rules", command)
            self.assertIn("--ephemeral", command)
            self.assertEqual(command[command.index("--sandbox") + 1], "read-only")
            self.assertEqual(command[command.index("--model") + 1], "gpt-5.6-luna")
            self.assertNotIn("api.openai.com", " ".join(command).lower())
            self.assertNotIn("bearer", " ".join(command).lower())
            self.assertEqual(command[-1], "-")
            self.assertIn("Return a proposal", kwargs["input"])

    def test_image_is_passed_as_a_codex_attachment_not_encoded_for_an_api(self) -> None:
        executor = RecordingExecutor()
        runner = oauth_codex.CodexOAuthRunner(executor=executor, environ={})
        schema = {"type": "object", "properties": {}, "additionalProperties": True}

        runner.invoke("follower", "Inspect frame.", schema, image_path=Path("frame.jpg"))

        command = executor.calls[-1][0]
        self.assertEqual(command[command.index("--image") + 1], str(Path("frame.jpg").resolve()))

    def test_malformed_structured_output_is_rejected(self) -> None:
        executor = RecordingExecutor(response={"ok": True})

        def write_invalid(command: list[str], **kwargs) -> subprocess.CompletedProcess[str]:
            if command[-2:] == ["login", "status"]:
                return executor(command, **kwargs)
            output_path = Path(command[command.index("--output-last-message") + 1])
            output_path.write_text("not-json", encoding="utf-8")
            return subprocess.CompletedProcess(command, 0, "", "")

        runner = oauth_codex.CodexOAuthRunner(executor=write_invalid, environ={})

        with self.assertRaisesRegex(RuntimeError, "invalid structured JSON"):
            runner.invoke("leader", "Return JSON.", {"type": "object"})


if __name__ == "__main__":
    unittest.main()
