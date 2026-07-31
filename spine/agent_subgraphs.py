"""Isolated LangGraph child agents backed by the official Codex SDK client."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from collections.abc import Callable, Mapping
from typing import Any, Literal, Protocol, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.runtime import Runtime

from codex_sdk_client import CodexAgentClient


LEADER_SCHEMA = {
    "type": "object",
    "properties": {
        "intent": {"type": "string"},
        "option": {"type": ["integer", "null"], "minimum": 1},
        "reason": {"type": "string"},
    },
    "required": ["intent", "option", "reason"],
    "additionalProperties": False,
}

MENU_LEADER_SCHEMA = {
    "type": "object",
    "properties": {
        "screen": {
            "type": "string",
            "enum": [
                "WARNING",
                "TITLE",
                "MAIN_MENU",
                "CHARACTER_SELECT",
                "STAGE_SELECT",
                "IN_GAME",
                "LEVEL_UP",
                "UNKNOWN",
            ],
        },
        "action": {
            "type": "string",
            "enum": [
                "up",
                "down",
                "left",
                "right",
                "confirm",
                "esc",
                "start",
                "click",
                "wait",
            ],
        },
        "click": {
            "type": ["array", "null"],
            "items": {"type": "integer"},
            "minItems": 2,
            "maxItems": 2,
        },
        "ready_for_run": {"type": "boolean"},
        "reason": {"type": "string"},
    },
    "required": ["screen", "action", "click", "ready_for_run", "reason"],
    "additionalProperties": False,
    # NOTE: no `allOf`/`if`/`then`/`else` conditional here. The Codex SDK's
    # `output_schema` rejects those keywords (invalid_json_schema). The
    # click-when-action=click invariant is enforced deterministically by
    # SpineGameTools.menu_action, which validates coordinates and presence.
}

FOLLOWER_SCHEMA = {
    "type": "object",
    "properties": {
        "direction": {
            "type": "string",
            "enum": ["N", "NE", "E", "SE", "S", "SW", "W", "NW", "HOLD"],
        },
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "reason": {"type": "string"},
    },
    "required": ["direction", "confidence", "reason"],
    "additionalProperties": False,
}


class GameTools(Protocol):
    def prepare(self) -> dict: ...
    def observe(self) -> dict: ...
    def checkpoint_state(self) -> dict: ...
    def restore_checkpoint(self, state: dict) -> bool: ...
    def menu_action(self, action: str, click=None) -> dict: ...
    def mark_in_game(self) -> None: ...
    def submit_direction(self, direction: str, latency_ms: float) -> bool: ...
    def control_window(self, seconds: float) -> dict: ...
    def select_level_up(self, option: int) -> dict: ...
    def evaluate(self, goal: str, run_id: str) -> dict: ...
    def evaluate_entry(self, run_id: str) -> dict: ...
    def neutralize(self) -> None: ...


def checkpoint_thread_bindings(state: Mapping[str, Any]) -> dict[str, str]:
    """Extract the only accepted Codex resume authority from graph state."""

    ambiguous_keys = ("thread_bindings", "codex_thread_bindings", "codex_thread_id")
    if any(state.get(key) is not None for key in ambiguous_keys):
        raise ValueError("checkpoint contains ambiguous Codex thread binding state")
    bindings: dict[str, str] = {}
    for role, field_name in (
        ("leader", "leader_codex_thread_id"),
        ("follower", "follower_codex_thread_id"),
    ):
        thread_id = state.get(field_name)
        if thread_id is None:
            continue
        if not isinstance(thread_id, str) or not thread_id.strip():
            raise ValueError(f"checkpoint {role} thread binding must be a non-empty string")
        bindings[role] = thread_id
    if len(set(bindings.values())) != len(bindings):
        raise ValueError("checkpoint thread bindings must be distinct by role")
    return bindings


@dataclass(frozen=True, slots=True)
class AgentRuntime:
    """Parent-only dependencies supplied through LangGraph runtime context."""

    codex: CodexAgentClient
    tools: GameTools

    @classmethod
    def from_checkpoint(
        cls,
        state: Mapping[str, Any],
        tools: GameTools,
        *,
        codex_factory: Callable[..., CodexAgentClient] = CodexAgentClient,
        **codex_options: Any,
    ) -> "AgentRuntime":
        bindings = checkpoint_thread_bindings(state)
        codex = codex_factory(thread_bindings=bindings, **codex_options)
        return cls(codex=codex, tools=tools)


@dataclass(frozen=True, slots=True)
class AgentModelRuntime:
    """The only dependency visible within either model child graph."""

    codex: CodexAgentClient


class LeaderInput(TypedDict):
    leader_goal: str
    leader_observation: dict[str, Any]
    leader_eval_contract: dict[str, Any]
    leader_decision_kind: Literal["gameplay", "menu"]
    leader_menu_steps_left: int | None
    leader_thread_id: str | None


class LeaderOutput(TypedDict):
    leader_decision: dict[str, Any]
    leader_thread_id: str
    leader_turn_id: str
    leader_usage: dict[str, Any] | None


class LeaderState(LeaderInput, LeaderOutput):
    pass


class FollowerInput(TypedDict):
    follower_goal: str
    follower_observation: dict[str, Any]
    follower_leader_decision: dict[str, Any]
    follower_thread_id: str | None


class FollowerOutput(TypedDict):
    follower_proposal: dict[str, Any]
    follower_thread_id: str
    follower_turn_id: str
    follower_usage: dict[str, Any] | None


class FollowerState(FollowerInput, FollowerOutput):
    pass


def _image_path(observation: dict[str, Any]) -> Path | None:
    image_value = observation.get("image_path")
    return Path(image_value) if image_value else None


def _contract_blurb(contract: dict[str, Any]) -> str:
    modifiers = contract.get("modifiers") or {}
    return (
        f"Fixed eval contract: character={contract.get('character', 'Antonio')}, "
        f"stage={contract.get('stage', 'Mad Forest')}, "
        f"modifiers={json.dumps(modifiers, sort_keys=True)}. "
        "Enforce this contract before starting a run. "
        "OCR hints in the observation are unreliable; trust the screenshot."
    )


async def _invoke_leader(
    state: LeaderState,
    runtime: Runtime[AgentModelRuntime],
) -> LeaderOutput:
    observation = state["leader_observation"]
    if state["leader_decision_kind"] == "menu":
        prompt = (
            f"Goal: {state['leader_goal']}\n"
            f"{_contract_blurb(state['leader_eval_contract'])}\n"
            f"Menu steps remaining: {state['leader_menu_steps_left']}\n"
            "Observation (hints are non-authoritative): "
            f"{json.dumps(observation, sort_keys=True)}\n"
            "You are navigating pre-run menus from the screenshot. "
            "Return exactly one action. Prefer keyboard actions "
            "(up/down/left/right/confirm/esc/start). Use click with frame "
            "[x,y] only when a key clearly cannot select the target. "
            "Set ready_for_run true only when the screenshot already shows "
            "an in-game HUD or level-up overlay after Antonio + Mad Forest "
            "with the required modifiers."
        )
        schema = MENU_LEADER_SCHEMA
    else:
        prompt = (
            f"Goal: {state['leader_goal']}\n"
            f"{_contract_blurb(state['leader_eval_contract'])}\n"
            f"Observation: {json.dumps(observation, sort_keys=True)}\n"
            "Return the high-level intent. On LEVEL_UP, option must be the "
            "one-based option index. Otherwise option must be null."
        )
        schema = LEADER_SCHEMA
    invocation = await runtime.context.codex.invoke(
        "leader",
        prompt,
        schema,
        image_path=_image_path(observation),
        thread_id=state["leader_thread_id"],
    )
    return {
        "leader_decision": invocation.payload,
        "leader_thread_id": invocation.thread_id,
        "leader_turn_id": invocation.turn_id,
        "leader_usage": invocation.usage,
    }


async def _invoke_follower(
    state: FollowerState,
    runtime: Runtime[AgentModelRuntime],
) -> FollowerOutput:
    observation = state["follower_observation"]
    prompt = (
        f"Goal: {state['follower_goal']}\n"
        "Leader intent: "
        f"{json.dumps(state['follower_leader_decision'], sort_keys=True)}\n"
        f"Observation: {json.dumps(observation, sort_keys=True)}\n"
        "Return one movement proposal. The deterministic controller may veto it."
    )
    invocation = await runtime.context.codex.invoke(
        "follower",
        prompt,
        FOLLOWER_SCHEMA,
        image_path=_image_path(observation),
        thread_id=state["follower_thread_id"],
    )
    return {
        "follower_proposal": invocation.payload,
        "follower_thread_id": invocation.thread_id,
        "follower_turn_id": invocation.turn_id,
        "follower_usage": invocation.usage,
    }


def build_leader_subgraph():
    """Compile one per-invocation leader child graph."""

    graph = StateGraph(
        LeaderState,
        context_schema=AgentModelRuntime,
        input_schema=LeaderInput,
        output_schema=LeaderOutput,
    )
    graph.add_node("invoke_codex_leader", _invoke_leader)
    graph.add_edge(START, "invoke_codex_leader")
    graph.add_edge("invoke_codex_leader", END)
    return graph.compile(name="leader_agent")


def build_follower_subgraph():
    """Compile one per-invocation follower child graph."""

    graph = StateGraph(
        FollowerState,
        context_schema=AgentModelRuntime,
        input_schema=FollowerInput,
        output_schema=FollowerOutput,
    )
    graph.add_node("invoke_codex_follower", _invoke_follower)
    graph.add_edge(START, "invoke_codex_follower")
    graph.add_edge("invoke_codex_follower", END)
    return graph.compile(name="follower_agent")
