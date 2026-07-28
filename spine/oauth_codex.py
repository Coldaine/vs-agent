"""Structured model calls through Codex's existing ChatGPT Pro OAuth login.

CHATGPT PRO OAUTH ONLY. This module never accepts an API key, never calls an
OpenAI-compatible HTTP endpoint, and never reads Codex's OAuth credential
files. Authentication remains entirely owned by the installed ``codex`` CLI.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping


FORBIDDEN_API_KEYS = (
    "OPENAI_API_KEY",
    "OPENROUTER_API_KEY",
    "DEEPSEEK_API_KEY",
)


def assert_oauth_only_environment(environ: Mapping[str, str] | None = None) -> None:
    """Fail closed if an API-backed model path could be selected accidentally."""

    values = os.environ if environ is None else environ
    present = [name for name in FORBIDDEN_API_KEYS if values.get(name)]
    if present:
        joined = ", ".join(present)
        raise RuntimeError(
            "ChatGPT Pro OAuth only: remove API-key variables from the "
            f"LangGraph process ({joined})"
        )


@dataclass(frozen=True)
class CodexOAuthConfig:
    executable: str = "codex"
    model: str = "gpt-5.6-luna"
    timeout_s: float = 120.0


Executor = Callable[..., subprocess.CompletedProcess[str]]


class CodexOAuthRunner:
    """Invoke leader/follower models via ``codex exec`` and ChatGPT OAuth."""

    def __init__(
        self,
        config: CodexOAuthConfig | None = None,
        *,
        executor: Executor = subprocess.run,
        environ: Mapping[str, str] | None = None,
        executable_resolver: Callable[[str], str | None] = shutil.which,
    ) -> None:
        self.config = config or CodexOAuthConfig()
        self._executor = executor
        self._environ = os.environ if environ is None else environ
        self._executable = executable_resolver(self.config.executable)
        if not self._executable:
            raise RuntimeError(
                "Codex CLI executable was not found on PATH; ChatGPT Pro OAuth "
                "cannot be used until Codex is installed"
            )
        self._login_checked = False
        assert_oauth_only_environment(self._environ)

    def check_login(self) -> None:
        """Verify Codex reports ChatGPT login without inspecting credentials."""

        result = self._executor(
            [self._executable, "login", "status"],
            capture_output=True,
            text=True,
            timeout=self.config.timeout_s,
            check=False,
        )
        combined = f"{result.stdout}\n{result.stderr}"
        if result.returncode != 0 or "Logged in using ChatGPT" not in combined:
            raise RuntimeError(
                "Codex is not ChatGPT OAuth authenticated; run `codex login` "
                "and choose ChatGPT login. API-key authentication is forbidden."
            )
        self._login_checked = True

    def invoke(
        self,
        role: str,
        prompt: str,
        schema: dict | None,
        image_path: Path | None = None,
    ) -> dict:
        """Return one schema-constrained Luna response for a named role."""

        if role not in {"leader", "follower"}:
            raise ValueError(f"unsupported OAuth model role: {role}")
        assert_oauth_only_environment(self._environ)
        if not self._login_checked:
            self.check_login()

        with tempfile.TemporaryDirectory(prefix="vs-agent-oauth-") as temp_name:
            temp_dir = Path(temp_name)
            schema_path = temp_dir / "output.schema.json"
            output_path = temp_dir / "output.json"
            if schema is not None:
                schema_path.write_text(json.dumps(schema), encoding="utf-8")

            command = [
                self._executable,
                "exec",
                "--ignore-user-config",
                "--ignore-rules",
                "--ephemeral",
                "--sandbox",
                "read-only",
                "--skip-git-repo-check",
                "--model",
                self.config.model,
                "--json",
                "--output-last-message",
                str(output_path),
            ]
            if schema is not None:
                command.extend(["--output-schema", str(schema_path)])
            if image_path is not None:
                command.extend(["--image", str(image_path.resolve())])
            command.append("-")

            guarded_prompt = (
                f"You are the {role} in a Vampire Survivors control system. "
                "Do not call tools or inspect files. Use only the supplied prompt "
                "and attached image. Return only the requested structured result.\n\n"
                f"{prompt}"
            )
            for attempt in range(2):
                if output_path.exists():
                    output_path.unlink()
                result = self._executor(
                    command,
                    input=guarded_prompt,
                    capture_output=True,
                    text=True,
                    timeout=self.config.timeout_s,
                    check=False,
                    cwd=temp_dir,
                )
                if result.returncode != 0:
                    raise RuntimeError(
                        f"Codex OAuth {role} invocation failed with exit code "
                        f"{result.returncode}: {result.stderr.strip()}"
                    )
                model_error = self._inspect_event_stream(result.stdout)
                if model_error is None:
                    break
                if attempt == 1:
                    raise RuntimeError(
                        f"Codex OAuth {role} reported an error after one retry: "
                        f"{model_error}"
                    )
            try:
                payload = json.loads(output_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as error:
                raise RuntimeError(
                    f"Codex OAuth {role} returned invalid structured JSON"
                ) from error
            if not isinstance(payload, dict):
                raise RuntimeError(
                    f"Codex OAuth {role} returned a non-object JSON result"
                )
            return payload

    @staticmethod
    def _inspect_event_stream(stdout: str) -> str | None:
        """Reject tool calls and return a retryable Codex model error, if any."""

        allowed = {"agent_message", "reasoning"}
        for line in stdout.splitlines():
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            item = event.get("item")
            if not isinstance(item, dict):
                continue
            item_type = item.get("type")
            if item_type == "error":
                return str(
                    item.get("message")
                    or item.get("text")
                    or item.get("error")
                    or "unspecified Codex model error"
                )
            if item_type not in allowed:
                raise RuntimeError(
                    "Codex OAuth role attempted forbidden tool activity: "
                    f"{item_type}"
                )
        return None
