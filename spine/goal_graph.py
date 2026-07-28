"""Durable LangGraph orchestration for a bounded Vampire Survivors goal.

LangGraph owns model turns, phase transitions, and checkpoint state. Models
only propose structured decisions. The injected game tools retain deterministic
authority over capture, input, safety, and evidence.

Pre-run menus are vision-led: the leader sees a screenshot and proposes one
menu action at a time. OCR hints in the observation are never transition gates.
"""

from __future__ import annotations

import time
from typing import Any, Literal, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.runtime import Runtime

from agent_subgraphs import (
    FOLLOWER_SCHEMA,
    LEADER_SCHEMA,
    MENU_LEADER_SCHEMA,
    AgentModelRuntime,
    AgentRuntime,
    GameTools,
    build_follower_subgraph,
    build_leader_subgraph,
    checkpoint_thread_bindings,
)


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
    leader_codex_thread_id: str | None
    follower_codex_thread_id: str | None


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
        "leader_codex_thread_id": None,
        "follower_codex_thread_id": None,
    }


def build_goal_graph(
    checkpointer,
    *,
    pause_after_observe: bool = False,
    pause_after_leader: bool = False,
    clock=time.monotonic,
):
    """Compile the parent graph; dependencies arrive only through context."""

    leader_subgraph = build_leader_subgraph()
    follower_subgraph = build_follower_subgraph()

    def _runtime_tools(runtime: Runtime[AgentRuntime]) -> GameTools:
        return runtime.context.tools

    def _assert_runtime_bindings(
        state: GoalState,
        runtime: Runtime[AgentRuntime],
    ) -> None:
        expected = checkpoint_thread_bindings(state)
        actual = runtime.context.codex.thread_bindings
        if actual != expected:
            raise RuntimeError(
                "checkpoint and runtime Codex thread bindings do not match exactly"
            )

    def prepare(state: GoalState, runtime: Runtime[AgentRuntime]) -> dict:
        tools = _runtime_tools(runtime)
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

    def observe(state: GoalState, runtime: Runtime[AgentRuntime]) -> dict:
        return {"phase": "observed", "observation": _runtime_tools(runtime).observe()}

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

    async def menu_leader(
        state: GoalState,
        runtime: Runtime[AgentRuntime],
    ) -> dict:
        tools = _runtime_tools(runtime)
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
        _assert_runtime_bindings(state, runtime)
        try:
            result = await leader_subgraph.ainvoke(
                {
                    "leader_goal": state["goal"],
                    "leader_observation": state["observation"] or {},
                    "leader_eval_contract": state.get("eval_contract") or {},
                    "leader_decision_kind": "menu",
                    "leader_menu_steps_left": state["menu_steps_left"],
                    "leader_thread_id": state.get("leader_codex_thread_id"),
                },
                context=AgentModelRuntime(codex=runtime.context.codex),
            )
        except Exception:
            tools.neutralize()
            raise
        return {
            "phase": "menu_planned",
            "leader_decision": result["leader_decision"],
            "leader_codex_thread_id": result["leader_thread_id"],
        }

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

    def promote_in_game(state: GoalState, runtime: Runtime[AgentRuntime]) -> dict:
        decision = state["leader_decision"] or {}
        claimed = str(decision.get("screen") or "IN_GAME")
        _runtime_tools(runtime).mark_in_game()
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

    def evaluate_entry(state: GoalState, runtime: Runtime[AgentRuntime]) -> dict:
        tools = _runtime_tools(runtime)
        result = tools.evaluate_entry(str(state["run_id"]))
        tools.neutralize()
        return {
            "phase": str(result.get("status", "achieved")),
            "status": str(result.get("status", "achieved")),
            "reason": str(result.get("reason", "vision reached in-game")),
            "evidence": [*state["evidence"], *result.get("evidence", [])],
        }

    def menu_action(state: GoalState, runtime: Runtime[AgentRuntime]) -> dict:
        tools = _runtime_tools(runtime)
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

    async def leader(state: GoalState, runtime: Runtime[AgentRuntime]) -> dict:
        _assert_runtime_bindings(state, runtime)
        tools = _runtime_tools(runtime)
        try:
            result = await leader_subgraph.ainvoke(
                {
                    "leader_goal": state["goal"],
                    "leader_observation": state["observation"] or {},
                    "leader_eval_contract": state.get("eval_contract") or {},
                    "leader_decision_kind": "gameplay",
                    "leader_menu_steps_left": None,
                    "leader_thread_id": state.get("leader_codex_thread_id"),
                },
                context=AgentModelRuntime(codex=runtime.context.codex),
            )
        except Exception:
            tools.neutralize()
            raise
        return {
            "phase": "planned",
            "leader_decision": result["leader_decision"],
            "leader_codex_thread_id": result["leader_thread_id"],
        }

    def route_leader(state: GoalState) -> str:
        screen_type = str((state["observation"] or {}).get("screen_type"))
        return "select_level_up" if screen_type == "LEVEL_UP" else "follower"

    async def follower(state: GoalState, runtime: Runtime[AgentRuntime]) -> dict:
        _assert_runtime_bindings(state, runtime)
        tools = _runtime_tools(runtime)
        started = clock()
        try:
            result = await follower_subgraph.ainvoke(
                {
                    "follower_goal": state["goal"],
                    "follower_observation": state["observation"] or {},
                    "follower_leader_decision": state["leader_decision"] or {},
                    "follower_thread_id": state.get("follower_codex_thread_id"),
                },
                context=AgentModelRuntime(codex=runtime.context.codex),
            )
        except Exception:
            tools.neutralize()
            raise
        proposal = {
            **result["follower_proposal"],
            "latency_ms": (clock() - started) * 1000.0,
        }
        return {
            "phase": "proposed",
            "follower_proposal": proposal,
            "follower_codex_thread_id": result["follower_thread_id"],
        }

    def control(state: GoalState, runtime: Runtime[AgentRuntime]) -> dict:
        tools = _runtime_tools(runtime)
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

    def select_level_up(state: GoalState, runtime: Runtime[AgentRuntime]) -> dict:
        tools = _runtime_tools(runtime)
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

    def evaluate(state: GoalState, runtime: Runtime[AgentRuntime]) -> dict:
        tools = _runtime_tools(runtime)
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

    def blocked(state: GoalState, runtime: Runtime[AgentRuntime]) -> dict:
        observation = state["observation"] or {}
        _runtime_tools(runtime).neutralize()
        reason = state.get("reason") or observation.get(
            "summary", "unknown or unsafe screen state"
        )
        return {
            "phase": "blocked",
            "status": "blocked",
            "reason": str(reason),
        }

    graph = StateGraph(GoalState, context_schema=AgentRuntime)
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

    interrupt_after = []
    if pause_after_observe:
        interrupt_after.append("observe")
    if pause_after_leader:
        interrupt_after.append("leader")
    return graph.compile(checkpointer=checkpointer, interrupt_after=interrupt_after)


async def run_goal(
    graph,
    goal: str,
    thread_id: str,
    runtime: AgentRuntime,
    *,
    retries: int = 0,
) -> GoalState:
    """Run or resume a goal under one durable LangGraph thread ID."""

    config = {
        "configurable": {"thread_id": thread_id},
        "recursion_limit": 1000,
    }
    snapshot = graph.get_state(config)
    if snapshot.values:
        return await graph.ainvoke(None, config, context=runtime)
    return await graph.ainvoke(
        initial_state(goal, retries=retries), config, context=runtime
    )
