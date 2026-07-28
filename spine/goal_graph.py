"""Durable LangGraph orchestration for a bounded Vampire Survivors goal.

LangGraph owns model turns, phase transitions, and checkpoint state. Models
only propose structured decisions. The injected game tools retain deterministic
authority over capture, input, safety, and evidence.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Literal, Protocol, TypedDict

from langgraph.graph import END, START, StateGraph


GoalStatus = Literal["running", "achieved", "not_met", "blocked"]


class GoalState(TypedDict):
    goal: str
    phase: str
    status: GoalStatus
    reason: str
    run_id: str | None
    observation: dict[str, Any] | None
    leader_decision: dict[str, Any] | None
    follower_proposal: dict[str, Any] | None
    evidence: list[str]
    retries_left: int


class ModelRunner(Protocol):
    def invoke(
        self,
        role: str,
        prompt: str,
        schema: dict,
        image_path=None,
    ) -> dict: ...


class GameTools(Protocol):
    def prepare(self) -> dict: ...
    def observe(self) -> dict: ...
    def submit_direction(self, direction: str, latency_ms: float) -> bool: ...
    def control_window(self, seconds: float) -> dict: ...
    def select_level_up(self, option: int) -> dict: ...
    def evaluate(self, goal: str, run_id: str) -> dict: ...
    def neutralize(self) -> None: ...


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


def initial_state(goal: str, *, retries: int = 0) -> GoalState:
    if not goal.strip():
        raise ValueError("goal must not be empty")
    if retries < 0:
        raise ValueError("retries must be non-negative")
    return {
        "goal": goal.strip(),
        "phase": "begin",
        "status": "running",
        "reason": "",
        "run_id": None,
        "observation": None,
        "leader_decision": None,
        "follower_proposal": None,
        "evidence": [],
        "retries_left": retries,
    }


def build_goal_graph(
    model_runner: ModelRunner,
    tools: GameTools,
    checkpointer,
    *,
    pause_after_observe: bool = False,
    clock=time.monotonic,
):
    """Compile the goal graph with an injected model and game boundary."""

    def prepare(state: GoalState) -> dict:
        prepared = tools.prepare()
        if not prepared.get("verified"):
            tools.neutralize()
            return {
                "phase": "blocked",
                "status": "blocked",
                "reason": prepared.get("reason", "fixed conditions were not verified"),
            }
        return {
            "phase": "prepared",
            "run_id": str(prepared["run_id"]),
            "observation": None,
            "leader_decision": None,
            "follower_proposal": None,
        }

    def route_after_prepare(state: GoalState) -> str:
        return "blocked" if state["status"] == "blocked" else "observe"

    def observe(state: GoalState) -> dict:
        return {"phase": "observed", "observation": tools.observe()}

    def route_observation(state: GoalState) -> str:
        screen_type = str((state["observation"] or {}).get("screen_type", "UNKNOWN"))
        if screen_type in {"PLAY", "LEVEL_UP"}:
            return "leader"
        if screen_type in {"DEATH", "RUN_END"}:
            return "evaluate"
        return "blocked"

    def leader(state: GoalState) -> dict:
        observation = state["observation"] or {}
        prompt = (
            f"Goal: {state['goal']}\n"
            f"Observation: {json.dumps(observation, sort_keys=True)}\n"
            "Return the high-level intent. On LEVEL_UP, option must be the "
            "one-based option index. Otherwise option must be null."
        )
        image_value = observation.get("image_path")
        image_path = Path(image_value) if image_value else None
        decision = model_runner.invoke(
            "leader", prompt, LEADER_SCHEMA, image_path=image_path
        )
        return {"phase": "planned", "leader_decision": decision}

    def route_leader(state: GoalState) -> str:
        screen_type = str((state["observation"] or {}).get("screen_type"))
        return "select_level_up" if screen_type == "LEVEL_UP" else "follower"

    def follower(state: GoalState) -> dict:
        prompt = (
            f"Goal: {state['goal']}\n"
            f"Leader intent: {json.dumps(state['leader_decision'], sort_keys=True)}\n"
            f"Observation: {json.dumps(state['observation'], sort_keys=True)}\n"
            "Return one movement proposal. The deterministic controller may veto it."
        )
        image_value = (state["observation"] or {}).get("image_path")
        image_path = Path(image_value) if image_value else None
        started = clock()
        proposal = model_runner.invoke(
            "follower", prompt, FOLLOWER_SCHEMA, image_path=image_path
        )
        proposal = {**proposal, "latency_ms": (clock() - started) * 1000.0}
        return {"phase": "proposed", "follower_proposal": proposal}

    def control(state: GoalState) -> dict:
        direction = str((state["follower_proposal"] or {}).get("direction", ""))
        latency_ms = float((state["follower_proposal"] or {}).get("latency_ms", 0.0))
        if not tools.submit_direction(direction, latency_ms):
            tools.neutralize()
            return {
                "phase": "blocked",
                "status": "blocked",
                "reason": f"controller rejected follower direction {direction!r}",
            }
        result = tools.control_window(2.0)
        evidence = [*state["evidence"], *result.get("evidence", [])]
        if not result.get("safe", False):
            tools.neutralize()
            return {
                "phase": "blocked",
                "status": "blocked",
                "reason": result.get("reason", "control safety fault"),
                "evidence": evidence,
            }
        return {"phase": "controlled", "evidence": evidence}

    def route_control(state: GoalState) -> str:
        return "blocked_end" if state["status"] == "blocked" else "observe"

    def select_level_up(state: GoalState) -> dict:
        option = (state["leader_decision"] or {}).get("option")
        if not isinstance(option, int) or option < 1:
            tools.neutralize()
            return {
                "phase": "blocked",
                "status": "blocked",
                "reason": f"leader returned invalid level-up option {option!r}",
            }
        result = tools.select_level_up(option)
        return {
            "phase": "selected",
            "evidence": [*state["evidence"], *result.get("evidence", [])],
        }

    def route_level_up(state: GoalState) -> str:
        return "blocked_end" if state["status"] == "blocked" else "observe"

    def evaluate(state: GoalState) -> dict:
        result = tools.evaluate(state["goal"], str(state["run_id"]))
        tools.neutralize()
        status = str(result.get("status", "not_met"))
        if status not in {"achieved", "not_met", "blocked"}:
            status = "blocked"
        retries_left = state["retries_left"]
        phase = status
        if status == "not_met" and retries_left > 0:
            phase = "retry"
            retries_left -= 1
        return {
            "phase": phase,
            "status": "running" if phase == "retry" else status,
            "reason": str(result.get("reason", "goal evaluation returned no reason")),
            "evidence": [*state["evidence"], *result.get("evidence", [])],
            "retries_left": retries_left,
        }

    def route_evaluation(state: GoalState) -> str:
        return "prepare" if state["phase"] == "retry" else "end"

    def blocked(state: GoalState) -> dict:
        observation = state["observation"] or {}
        tools.neutralize()
        return {
            "phase": "blocked",
            "status": "blocked",
            "reason": str(observation.get("summary", "unknown or unsafe screen state")),
        }

    graph = StateGraph(GoalState)
    graph.add_node("prepare", prepare)
    graph.add_node("observe", observe)
    graph.add_node("leader", leader)
    graph.add_node("follower", follower)
    graph.add_node("control", control)
    graph.add_node("select_level_up", select_level_up)
    graph.add_node("evaluate", evaluate)
    graph.add_node("blocked", blocked)

    graph.add_edge(START, "prepare")
    graph.add_conditional_edges(
        "prepare", route_after_prepare, {"observe": "observe", "blocked": END}
    )
    graph.add_conditional_edges(
        "observe",
        route_observation,
        {"leader": "leader", "evaluate": "evaluate", "blocked": "blocked"},
    )
    graph.add_conditional_edges(
        "leader",
        route_leader,
        {"follower": "follower", "select_level_up": "select_level_up"},
    )
    graph.add_edge("follower", "control")
    graph.add_conditional_edges(
        "control", route_control, {"observe": "observe", "blocked_end": END}
    )
    graph.add_conditional_edges(
        "select_level_up",
        route_level_up,
        {"observe": "observe", "blocked_end": END},
    )
    graph.add_conditional_edges(
        "evaluate", route_evaluation, {"prepare": "prepare", "end": END}
    )
    graph.add_edge("blocked", END)

    interrupt_after = ["observe"] if pause_after_observe else None
    return graph.compile(checkpointer=checkpointer, interrupt_after=interrupt_after)


def run_goal(graph, goal: str, thread_id: str, *, retries: int = 0) -> GoalState:
    """Run or resume a goal under one durable LangGraph thread ID."""

    config = {
        "configurable": {"thread_id": thread_id},
        "recursion_limit": 1000,
    }
    snapshot = graph.get_state(config)
    if snapshot.values:
        return graph.invoke(None, config)
    return graph.invoke(initial_state(goal, retries=retries), config)
