"""No-game smoke for the real LangGraph + official Codex SDK model path.

The smoke invokes both child roles with ChatGPT-managed Codex authentication.
Only the deterministic game boundary is fake, and it emits no input.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from jsonschema import ValidationError, validate
from langgraph.checkpoint.memory import InMemorySaver
from openai_codex import AsyncCodex

from agent_subgraphs import (
    AgentRuntime,
    FOLLOWER_SCHEMA,
    LEADER_SCHEMA,
)
from codex_sdk_client import DEFAULT_MODEL, CodexAgentClient
from goal_graph import build_goal_graph, run_goal


CONFIGURED_MODEL = DEFAULT_MODEL
PARENT_THREAD_ID = "oauth-smoke"
DEFAULT_IMAGE_PATH = Path(__file__).resolve().parents[1] / "status" / "g0_capture.jpg"


def _field(value: Any, name: str) -> Any:
    if isinstance(value, Mapping):
        return value.get(name)
    return getattr(value, name, None)


def _enum_value(value: Any) -> Any:
    return getattr(value, "value", value)


class _ObservedThread:
    def __init__(self, inner: Any, owner: "_ConfiguredSdkContext") -> None:
        self._inner = inner
        self._owner = owner
        self.id = inner.id

    async def run(self, input_value: Any, **kwargs: Any) -> Any:
        result = await self._inner.run(input_value, **kwargs)
        fields = getattr(type(result), "model_fields", {})
        self._owner.turns[self.id] = {
            "turn_id": result.id,
            "image_attached": isinstance(input_value, list) and len(input_value) >= 2,
            "turn_result_echoed_model": "model" in fields,
        }
        return result


class _ConfiguredSdkContext:
    """Own one public SDK lifecycle while pinning and observing smoke turns."""

    def __init__(self, sdk_factory: Callable[[], Any], model: str) -> None:
        self._context = sdk_factory()
        self._sdk: Any | None = None
        self.model = model
        self.account_response: Any | None = None
        self.model_response: Any | None = None
        self.turns: dict[str, dict[str, Any]] = {}

    async def __aenter__(self) -> "_ConfiguredSdkContext":
        self._sdk = await self._context.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        self._sdk = None
        await self._context.__aexit__(exc_type, exc, traceback)

    def _require_sdk(self) -> Any:
        if self._sdk is None:
            raise RuntimeError("Codex SDK context is not active")
        return self._sdk

    async def account(self) -> Any:
        self.account_response = await self._require_sdk().account()
        return self.account_response

    async def models(self, *, include_hidden: bool = False) -> Any:
        self.model_response = await self._require_sdk().models(
            include_hidden=include_hidden
        )
        return self.model_response

    async def thread_start(self, **kwargs: Any) -> _ObservedThread:
        kwargs["model"] = self.model
        thread = await self._require_sdk().thread_start(**kwargs)
        return _ObservedThread(thread, self)

    async def thread_resume(self, thread_id: str, **kwargs: Any) -> _ObservedThread:
        kwargs["model"] = self.model
        thread = await self._require_sdk().thread_resume(thread_id, **kwargs)
        return _ObservedThread(thread, self)


def validate_smoke_result(result: dict) -> dict:
    """Reject incomplete or overstated real-smoke evidence."""

    try:
        if result.get("contract_version") != 1:
            raise ValueError("unsupported smoke contract version")
        if result.get("status") != "achieved":
            raise ValueError("smoke did not achieve its no-game goal")
        account = result["account"]
        if account.get("type") != "chatgpt" or account.get("plan_type") != "pro":
            raise ValueError("public account metadata must prove ChatGPT Pro authentication")
        model = result["model"]
        if (
            model.get("configured") != CONFIGURED_MODEL
            or model.get("catalog_available") is not True
        ):
            raise ValueError("configured model must be publicly available in the catalog")
        if not {"text", "image"}.issubset(
            set(model.get("catalog_input_modalities") or [])
        ):
            raise ValueError("configured model catalog entry must support text and image")
        if model.get("turn_result_echoed_model") is not False:
            raise ValueError("smoke must not claim TurnResult echoed a model field")
        graph = result["langgraph"]
        if not graph.get("parent_thread_id"):
            raise ValueError("parent LangGraph thread ID is required")
        if graph.get("child_graphs") != ["leader_agent", "follower_agent"]:
            raise ValueError("both separately compiled child graph names are required")
        roles = result["roles"]
        if set(roles) != {"leader", "follower"}:
            raise ValueError("leader and follower role evidence is required")
        for role in roles:
            if roles[role].get("graph_name") != f"{role}_agent":
                raise ValueError(f"{role} child graph name is invalid")
            if not roles[role].get("turn_id"):
                raise ValueError(f"{role} turn ID is required")
        thread_ids = [roles[role].get("codex_thread_id") for role in roles]
        if any(not value for value in thread_ids) or len(set(thread_ids)) != 2:
            raise ValueError("role Codex thread IDs must be non-empty and distinct")
        for role, schema in (("leader", LEADER_SCHEMA), ("follower", FOLLOWER_SCHEMA)):
            if roles[role].get("schema_valid") is not True:
                raise ValueError(f"{role} decision was not schema-valid")
            validate(instance=roles[role].get("decision"), schema=schema)
        image = result["image"]
        if image.get("role") not in roles:
            raise ValueError("image evidence must identify a completed child role")
        if image.get("attached") is not True or image.get("schema_valid") is not True:
            raise ValueError("image turn did not produce schema-valid attached evidence")
        if result["game_input"].get("emitted") is not False:
            raise ValueError("no-game smoke emitted game input")
    except (KeyError, TypeError, ValidationError) as error:
        raise ValueError("invalid real OAuth smoke result") from error
    return result


class SmokeGameTools:
    def __init__(self, image_path: Path) -> None:
        self.observations = [
            {
                "screen_type": "PLAY",
                "summary": "synthetic safe play state; image is the observation",
                "image_path": str(image_path),
            },
            {"screen_type": "RUN_END", "summary": "synthetic run end"},
        ]
        self.emitted_input = False

    def prepare(self) -> dict:
        return {"verified": True, "run_id": "oauth-smoke", "entry_only": False}

    def observe(self) -> dict:
        return self.observations.pop(0)

    def menu_action(self, action: str, click=None) -> dict:
        raise AssertionError("smoke never enters menu navigation")

    def mark_in_game(self) -> None:
        return None

    def submit_direction(self, direction: str, latency_ms: float) -> bool:
        return direction in {"N", "NE", "E", "SE", "S", "SW", "W", "NW", "HOLD"}

    def control_window(self, seconds: float) -> dict:
        return {"safe": seconds == 2.0, "evidence": ["smoke-control"]}

    def select_level_up(self, option: int) -> dict:
        raise AssertionError("smoke observation never enters LEVEL_UP")

    def evaluate(self, goal: str, run_id: str) -> dict:
        return {
            "status": "achieved",
            "reason": "both SDK child roles completed with deterministic tools",
            "evidence": ["smoke-outcome"],
        }

    def evaluate_entry(self, run_id: str) -> dict:
        raise AssertionError("smoke is not entry-only")

    def neutralize(self) -> None:
        return None


async def run_smoke(
    *,
    sdk_factory: Callable[[], Any] = AsyncCodex,
    codex_factory: Callable[..., CodexAgentClient] = CodexAgentClient,
    image_path: Path = DEFAULT_IMAGE_PATH,
) -> dict:
    """Return validated public evidence from both child agents and one image."""

    image_path = image_path.resolve()
    if not image_path.is_file():
        raise FileNotFoundError(f"smoke image does not exist: {image_path}")
    tools = SmokeGameTools(image_path)
    sdk_context = _ConfiguredSdkContext(sdk_factory, CONFIGURED_MODEL)
    runtime = AgentRuntime.from_checkpoint(
        {},
        tools,
        codex_factory=codex_factory,
        sdk_factory=lambda: sdk_context,
    )
    graph = build_goal_graph(InMemorySaver())
    try:
        await runtime.codex.start()
        account_response = sdk_context.account_response
        model_response = await sdk_context.models(include_hidden=True)
        graph_result = await run_goal(
            graph,
            "Prove the leader and follower complete an official SDK smoke.",
            PARENT_THREAD_ID,
            runtime,
        )
        account_value = _field(account_response, "account")
        account_profile = _field(account_value, "root") or account_value
        models = list(_field(model_response, "data") or [])
        catalog_model = next(
            (
                model
                for model in models
                if CONFIGURED_MODEL
                in {_field(model, "id"), _field(model, "model")}
            ),
            None,
        )
        if catalog_model is None:
            available = sorted(
                {
                    str(_field(model, "model") or _field(model, "id"))
                    for model in models
                }
            )
            raise RuntimeError(
                f"configured model {CONFIGURED_MODEL!r} is absent from the public "
                f"SDK model catalog: {available}"
            )
        modalities = [
            str(_enum_value(value))
            for value in (_field(catalog_model, "input_modalities") or [])
        ]
        bindings = runtime.codex.thread_bindings
        role_evidence = {}
        for role, decision_field in (
            ("leader", "leader_decision"),
            ("follower", "follower_proposal"),
        ):
            thread_id = bindings[role]
            turn = sdk_context.turns[thread_id]
            decision = dict(graph_result[decision_field])
            decision.pop("latency_ms", None)
            role_evidence[role] = {
                "graph_name": f"{role}_agent",
                "codex_thread_id": thread_id,
                "turn_id": turn["turn_id"],
                "decision": decision,
                "schema_valid": True,
            }
        image_role = next(
            role
            for role in ("leader", "follower")
            if sdk_context.turns[bindings[role]]["image_attached"]
        )
        try:
            image_source = image_path.relative_to(Path(__file__).resolve().parents[1]).as_posix()
        except ValueError:
            image_source = image_path.name
        result = {
            "contract_version": 1,
            "status": graph_result["status"],
            "account": {
                "type": str(_enum_value(_field(account_profile, "type"))),
                "plan_type": str(_enum_value(_field(account_profile, "plan_type"))),
            },
            "model": {
                "configured": CONFIGURED_MODEL,
                "catalog_available": True,
                "catalog_input_modalities": modalities,
                "turn_result_echoed_model": any(
                    turn["turn_result_echoed_model"]
                    for turn in sdk_context.turns.values()
                ),
            },
            "langgraph": {
                "parent_thread_id": PARENT_THREAD_ID,
                "child_graphs": ["leader_agent", "follower_agent"],
            },
            "roles": role_evidence,
            "image": {
                "role": image_role,
                "attached": True,
                "source": image_source,
                "schema_valid": role_evidence[image_role]["schema_valid"],
            },
            "game_input": {"emitted": tools.emitted_input},
        }
        return validate_smoke_result(result)
    finally:
        try:
            tools.neutralize()
        finally:
            await runtime.codex.close()


def main() -> int:
    result = asyncio.run(run_smoke())
    print(json.dumps(result, sort_keys=True))
    return 0 if result["status"] == "achieved" else 2


if __name__ == "__main__":
    raise SystemExit(main())
