"""Narrow ChatGPT OAuth client boundary around the official Codex SDK."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jsonschema import ValidationError, validate
from jsonschema.exceptions import SchemaError
from openai_codex import (
    ApprovalMode,
    AsyncCodex,
    LocalImageInput,
    Sandbox,
    TextInput,
)


_RESTRICTED_CONFIG = {
    "web_search": "disabled",
    "features": {"shell_tool": False},
}
DEFAULT_MODEL = "gpt-5.6-luna"


@dataclass(frozen=True, slots=True)
class CodexInvocation:
    """One validated structured result from a Codex SDK turn."""

    payload: dict
    thread_id: str
    turn_id: str
    usage: dict | None


class CodexAgentClient:
    """Maintain one ChatGPT-authenticated SDK client for role invocations."""

    def __init__(
        self,
        *,
        sdk_factory: Callable[[], Any] = AsyncCodex,
        image_factory: Callable[[str], Any] = LocalImageInput,
        text_factory: Callable[[str], Any] = TextInput,
        model: str = DEFAULT_MODEL,
        sandbox: Sandbox = Sandbox.read_only,
        approval_mode: ApprovalMode = ApprovalMode.deny_all,
        thread_bindings: Mapping[str, str] | None = None,
    ) -> None:
        self._sdk_factory = sdk_factory
        self._image_factory = image_factory
        self._text_factory = text_factory
        if not model.strip():
            raise ValueError("model must be non-empty")
        self._model = model
        self._sandbox = sandbox
        self._approval_mode = approval_mode
        self._context: Any | None = None
        self._sdk: Any | None = None
        self._closed = False
        self._lifecycle_lock = asyncio.Lock()
        self._thread_lock = asyncio.Lock()
        self._thread_bindings = dict(thread_bindings or {})
        if len(set(self._thread_bindings.values())) != len(self._thread_bindings):
            raise ValueError("thread bindings must not assign one SDK thread to multiple roles")

    @property
    def thread_bindings(self) -> dict[str, str]:
        """Return the role-to-SDK-thread bindings to persist in checkpoint state."""

        return dict(self._thread_bindings)

    @property
    def configured_model(self) -> str:
        """Return the explicit SDK thread model configured by this client."""

        return self._model

    async def start(self) -> None:
        """Enter the SDK once and confirm it is using the existing ChatGPT login."""

        async with self._lifecycle_lock:
            if self._sdk is not None:
                return
            if self._closed:
                raise RuntimeError("Codex SDK client is closed")

            context = self._sdk_factory()
            sdk = await context.__aenter__()
            try:
                if not _is_chatgpt_managed_account(await sdk.account()):
                    raise RuntimeError("Codex SDK account is not ChatGPT-managed authentication")
            except Exception:
                await context.__aexit__(None, None, None)
                self._closed = True
                raise

            self._context = context
            self._sdk = sdk

    async def close(self) -> None:
        """Exit the owned SDK context once."""

        async with self._lifecycle_lock:
            if self._context is None or self._closed:
                return
            context = self._context
            self._context = None
            self._sdk = None
            self._closed = True
            await context.__aexit__(None, None, None)

    async def invoke(
        self,
        role: str,
        prompt: str,
        schema: dict,
        image_path: Path | None = None,
        thread_id: str | None = None,
    ) -> CodexInvocation:
        """Run one schema-constrained role turn without exposing auth material."""

        if not role.strip():
            raise ValueError("role must be non-empty")
        await self.start()
        if self._sdk is None:
            raise RuntimeError("Codex SDK client did not start")

        async with self._thread_lock:
            thread = await self._role_thread(role, thread_id)
        input_value: str | list[Any] = prompt
        if image_path is not None:
            input_value = [
                self._text_factory(prompt),
                self._image_factory(str(image_path)),
            ]
        turn = await thread.run(
            input_value,
            output_schema=schema,
            approval_mode=self._approval_mode,
            sandbox=self._sandbox,
        )
        payload = _parse_final_response(turn.final_response, schema)
        return CodexInvocation(
            payload=payload,
            thread_id=thread.id,
            turn_id=turn.id,
            usage=_usage_as_dict(turn.usage),
        )

    def _thread_options(self) -> dict[str, Any]:
        return {
            "approval_mode": self._approval_mode,
            "sandbox": self._sandbox,
            "config": _RESTRICTED_CONFIG,
            "model": self._model,
        }

    async def _role_thread(self, role: str, thread_id: str | None) -> Any:
        if self._sdk is None:
            raise RuntimeError("Codex SDK client did not start")
        if thread_id is not None:
            self._assert_thread_role(thread_id, role)
            thread = await self._sdk.thread_resume(thread_id, **self._thread_options())
            if thread.id != thread_id:
                raise RuntimeError("Codex SDK resumed an unexpected thread ID")
        else:
            thread = await self._sdk.thread_start(**self._thread_options())
        self._record_thread_role(thread.id, role)
        return thread

    def _assert_thread_role(self, thread_id: str, role: str) -> None:
        owner = self._role_for_thread(thread_id)
        if owner is None:
            raise RuntimeError("Codex thread ID is not registered for checkpoint resume")
        if owner != role:
            raise RuntimeError(
                f"Codex thread {thread_id!r} belongs to {owner!r}, not role {role!r}; "
                "resuming it under a different role is forbidden"
            )

    def _record_thread_role(self, thread_id: str, role: str) -> None:
        owner = self._role_for_thread(thread_id)
        if owner is not None and owner != role:
            raise RuntimeError(
                f"Codex thread {thread_id!r} belongs to {owner!r}, not role {role!r}"
            )
        self._thread_bindings[role] = thread_id

    def _role_for_thread(self, thread_id: str) -> str | None:
        return next(
            (role for role, bound_thread_id in self._thread_bindings.items()
             if bound_thread_id == thread_id),
            None,
        )


def _is_chatgpt_managed_account(metadata: Any) -> bool:
    """Accept only the SDK's public ChatGPT account representation."""

    account = _field(metadata, "account")
    profile = _field(account, "root") if account is not None else None
    if profile is None:
        profile = account
    return _field(profile, "type") == "chatgpt"


def _field(value: Any, name: str) -> Any:
    if isinstance(value, Mapping):
        return value.get(name)
    return getattr(value, name, None)


def _parse_final_response(final_response: Any, schema: dict) -> dict:
    if not isinstance(final_response, str):
        raise RuntimeError("Codex SDK returned invalid JSON final response")
    try:
        payload = json.loads(final_response)
    except json.JSONDecodeError as error:
        raise RuntimeError("Codex SDK returned invalid JSON final response") from error
    if not isinstance(payload, dict):
        raise RuntimeError("Codex SDK returned a non-object JSON final response")
    try:
        validate(instance=payload, schema=schema)
    except (SchemaError, ValidationError) as error:
        raise RuntimeError("Codex SDK final response failed schema validation") from error
    return payload


def _usage_as_dict(usage: Any) -> dict | None:
    if usage is None:
        return None
    if isinstance(usage, dict):
        return usage
    if hasattr(usage, "model_dump"):
        return usage.model_dump(mode="json")
    raise RuntimeError("Codex SDK returned unsupported usage metadata")
