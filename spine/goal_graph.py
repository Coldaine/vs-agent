"""Durable LangGraph orchestration for a bounded Vampire Survivors goal.

LangGraph owns model turns, phase transitions, and checkpoint state. Models
only propose structured decisions. The injected game tools retain deterministic
authority over capture, input, safety, and evidence.

Pre-run menus are vision-led: the leader sees a screenshot and proposes one
menu action at a time. OCR hints in the observation are never transition gates.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Literal, Protocol, TypedDict

from langgraph.graph import END, START, StateGraph


GoalStatus = Literal["running", "achieved", "not_met", "blocked"]

MENU_SCREENS = {
    "MENU",
    "WARNING",
    "TITLE",
    "MAIN_MENU",
    "CHARACTER_SELECT",
    "STAGE_SELECT",
    "UNKNOWN",
}


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
    menu_steps_left: int
    eval_contract: dict[str, Any]
    entry_only: bool


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
    def menu_action(self, action: str, click=None) -> dict: ...
    def mark_in_game(self) -> None: ...
    def submit_direction(self, direction: str, latency_ms: float) -> bool: ...
    def control_window(self, seconds: float) -> dict: ...
    def select_level_up(self, option: int) -> dict: ...
    def evaluate(self, goal: str, run_id: str) -> dict: ...
    def evaluate_entry(self, run_id: str) -> dict: ...
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
            "enum": ["up", "down", "left", "right", "confirm", "esc", "start", "click", "wait"],
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
        "menu_steps_left": 40,
        "eval_contract": {},
        "entry_only": False,
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
            "menu_steps_left": int(prepared.get("menu_steps_budget", 40)),
            "eval_contract": dict(prepared.get("eval_contract") or {}),
            "entry_only": bool(prepared.get("entry_only", False)),
        }

    def route_after_prepare(state: GoalState) -> str:
        return "blocked" if state["status"] == "blocked" else "observe"

    def observe(state: GoalState) -> dict:
        return {"phase": "observed", "observation": tools.observe()}

    def route_observation(state: GoalState) -> str:
        screen_type = str((state["observation"] or {}).get("screen_type", "UNKNOWN"))
        if screen_type == "SAFETY_FAULT":
            return "blocked"
        if screen_type in {"PLAY", "LEVEL_UP"}:
            if state.get("entry_only"):
                return "evaluate_entry"
            return "leader"
        if screen_type in {"DEATH", "RUN_END"}:
            return "evaluate"
        if screen_type in MENU_SCREENS:
            return "menu_leader"
        return "menu_leader"

    def _contract_blurb(state: GoalState) -> str:
        contract = state.get("eval_contract") or {}
        modifiers = contract.get("modifiers") or {}
        return (
            f"Fixed eval contract: character={contract.get('character', 'Antonio')}, "
            f"stage={contract.get('stage', 'Mad Forest')}, "
            f"modifiers={json.dumps(modifiers, sort_keys=True)}. "
            "Enforce this contract before starting a run. "
            "OCR hints in the observation are unreliable; trust the screenshot."
        )

    def menu_leader(state: GoalState) -> dict:
        if state["menu_steps_left"] <= 0:
            tools.neutralize()
            return {
                "phase": "blocked",
                "status": "blocked",
                "reason": "menu step budget exhausted before reaching in-game",
                "leader_decision": {
                    "screen": "UNKNOWN",
                    "action": "wait",
                    "click": None,
                    "ready_for_run": False,
                    "reason": "budget exhausted",
                },
            }
        observation = state["observation"] or {}
        prompt = (
            f"Goal: {state['goal']}\n"
            f"{_contract_blurb(state)}\n"
            f"Menu steps remaining: {state['menu_steps_left']}\n"
            f"Observation (hints are non-authoritative): "
            f"{json.dumps(observation, sort_keys=True)}\n"
            "You are navigating pre-run menus from the screenshot. "
            "Return exactly one action. Prefer keyboard actions "
            "(up/down/left/right/confirm/esc/start). Use click with frame "
            "[x,y] only when a key clearly cannot select the target. "
            "Set ready_for_run true only when the screenshot already shows "
            "an in-game HUD or level-up overlay after Antonio + Mad Forest "
            "with the required modifiers."
        )
        image_value = observation.get("image_path")
        image_path = Path(image_value) if image_value else None
        decision = model_runner.invoke(
            "leader", prompt, MENU_LEADER_SCHEMA, image_path=image_path
        )
        return {"phase": "menu_planned", "leader_decision": decision}

    def route_menu_leader(state: GoalState) -> str:
        if state["status"] == "blocked":
            return "blocked_end"
        decision = state["leader_decision"] or {}
        # Trust vision over OCR: leader may assert in-run while hints still say MENU.
        if decision.get("ready_for_run") and decision.get("screen") in {
            "IN_GAME",
            "LEVEL_UP",
        }:
            return "promote_in_game"
        return "menu_action"

    def promote_in_game(state: GoalState) -> dict:
        decision = state["leader_decision"] or {}
        claimed = str(decision.get("screen") or "IN_GAME")
        tools.mark_in_game()
        observation = dict(state["observation"] or {})
        observation["screen_type"] = "LEVEL_UP" if claimed == "LEVEL_UP" else "PLAY"
        observation["promoted_by_vision"] = True
        return {
            "phase": "in_game",
            "observation": observation,
            "evidence": [*state["evidence"], f"vision-promote:{claimed}"],
        }

    def route_promote(state: GoalState) -> str:
        return "evaluate_entry" if state.get("entry_only") else "leader"

    def evaluate_entry(state: GoalState) -> dict:
        result = tools.evaluate_entry(str(state["run_id"]))
        tools.neutralize()
        return {
            "phase": str(result.get("status", "achieved")),
            "status": str(result.get("status", "achieved")),
            "reason": str(result.get("reason", "vision reached in-game")),
            "evidence": [*state["evidence"], *result.get("evidence", [])],
        }

    def menu_action(state: GoalState) -> dict:
        decision = state["leader_decision"] or {}
        action = str(decision.get("action") or "wait")
        click = decision.get("click")
        steps_left = state["menu_steps_left"] - 1
        if action == "wait":
            return {
                "phase": "menu_acted",
                "menu_steps_left": steps_left,
                "evidence": [*state["evidence"], "menu:wait"],
            }
        try:
            result = tools.menu_action(action, click=click)
        except Exception as error:
            tools.neutralize()
            return {
                "phase": "blocked",
                "status": "blocked",
                "reason": f"menu action failed: {error}",
                "menu_steps_left": steps_left,
            }
        return {
            "phase": "menu_acted",
            "menu_steps_left": steps_left,
            "evidence": [*state["evidence"], *result.get("evidence", [])],
        }

    def route_menu_action(state: GoalState) -> str:
        return "blocked_end" if state["status"] == "blocked" else "observe"

    def leader(state: GoalState) -> dict:
        observation = state["observation"] or {}
        prompt = (
            f"Goal: {state['goal']}\n"
            f"{_contract_blurb(state)}\n"
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
        reason = state.get("reason") or observation.get(
            "summary", "unknown or unsafe screen state"
        )
        return {
            "phase": "blocked",
            "status": "blocked",
            "reason": str(reason),
        }

    graph = StateGraph(GoalState)
    graph.add_node("prepare", prepare)
    graph.add_node("observe", observe)
    graph.add_node("menu_leader", menu_leader)
    graph.add_node("menu_action", menu_action)
    graph.add_node("promote_in_game", promote_in_game)
    graph.add_node("evaluate_entry", evaluate_entry)
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
        {
            "leader": "leader",
            "menu_leader": "menu_leader",
            "evaluate": "evaluate",
            "evaluate_entry": "evaluate_entry",
            "blocked": "blocked",
        },
    )
    graph.add_conditional_edges(
        "menu_leader",
        route_menu_leader,
        {
            "menu_action": "menu_action",
            "promote_in_game": "promote_in_game",
            "blocked_end": END,
        },
    )
    graph.add_conditional_edges(
        "promote_in_game",
        route_promote,
        {"leader": "leader", "evaluate_entry": "evaluate_entry"},
    )
    graph.add_edge("evaluate_entry", END)
    graph.add_conditional_edges(
        "menu_action",
        route_menu_action,
        {"observe": "observe", "blocked_end": END},
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
