# Task 2 report: real LangGraph leader and follower subgraphs

## Status

Implemented and focused verification passed. The commit object ID is reported in the
Task 2 handoff because a file cannot embed the hash of the commit that contains it.

## Files

- Created `spine/agent_subgraphs.py`.
- Created `tests/test_agent_subgraphs.py`.
- Modified `spine/goal_graph.py`.
- Modified `tests/test_goal_graph.py`.
- Added this Task 2 report.
- Preserved and did not stage `GOAL.md`, `status/HUMAN_NEEDED.md`, and
  `status/g0_capture.jpg`.

## Interfaces

- `build_leader_subgraph()` and `build_follower_subgraph()` return distinct compiled
  child `StateGraph` instances named `leader_agent` and `follower_agent`.
- Both child graphs use default `checkpointer=None` inherited per-invocation
  checkpointing, async nodes, `ainvoke`, role-prefixed disjoint input/output schemas,
  and `AgentModelRuntime(codex)` context.
- `AgentRuntime(codex: CodexAgentClient, tools: GameTools)` is the parent runtime
  context. Parent wrappers map narrow state into each child and map only the validated
  proposal and role thread ID back.
- `GoalState` persists `leader_codex_thread_id` and
  `follower_codex_thread_id` separately.
- `AgentRuntime.from_checkpoint(...)` hydrates `CodexAgentClient` only from those two
  fields. Duplicate, empty, legacy/ambiguous, cross-role, missing, or extra runtime
  bindings are rejected before any SDK resume call.
- Game tools are structurally excluded from child context; only parent nodes can use
  them. Provider failures neutralize the game boundary before propagating.
- Parent execution and `run_goal` are async. Task 3 owns rewiring `run.py`, the old
  OAuth adapter, and compatibility smoke callers to this interface.

## TDD evidence

### RED 1: missing child module

Command:

```powershell
.venv\Scripts\python.exe -m unittest tests.test_agent_subgraphs -v
```

Result: exit 1. The test module failed to import with
`ModuleNotFoundError: No module named 'agent_subgraphs'`.

### GREEN 1: isolated child graphs

Command:

```powershell
.venv\Scripts\python.exe -m unittest tests.test_agent_subgraphs -v
```

Result: exit 0, 5 tests passed.

### RED 2: authoritative checkpoint runtime restoration

Command:

```powershell
.venv\Scripts\python.exe -m unittest tests.test_agent_subgraphs.AgentSubgraphTests.test_agent_runtime_restores_only_typed_role_checkpoint_bindings tests.test_agent_subgraphs.AgentSubgraphTests.test_agent_runtime_rejects_duplicate_or_ambiguous_checkpoint_bindings -v
```

Result: exit 1. Both behaviors failed because `agent_subgraphs.AgentRuntime` did not
exist.

### GREEN 2: child graphs plus restoration validation

Command:

```powershell
.venv\Scripts\python.exe -m unittest tests.test_agent_subgraphs -v
```

Result: exit 0, 7 tests passed.

### RED 3: async parent child wrappers and resume checkpoint

Command:

```powershell
.venv\Scripts\python.exe -m unittest tests.test_goal_graph.ParentSubgraphTests -v
```

Result: exit 1, 2 errors. The old parent required
`build_goal_graph(model_runner, tools, checkpointer)` and had no
`pause_after_leader` support.

### GREEN 3: focused Task 2 graph verification

Command:

```powershell
.venv\Scripts\python.exe -m unittest tests.test_agent_subgraphs tests.test_goal_graph -v
```

Result: exit 0, 19 tests passed. This includes child namespace discovery, resume
without repeated leader work, cross-role rejection before SDK invocation, menu/G0
routing preservation, and async SQLite checkpoint rebuild/resume.

## Self-review

- Confirmed the child builders take no game-tool dependency and their runtime schema
  has only the Codex client.
- Confirmed the parent compares the complete live client registry with the two typed
  checkpoint fields before every model child call.
- Confirmed leader and follower IDs cannot alias and no generic binding map or token
  storage was added.
- Confirmed prompt behavior, image forwarding, menu step budget, controller veto,
  evidence handling, and G0 vision promotion remain covered.
- Confirmed completed leader work survives a parent interrupt and is not invoked again
  on resume; the inherited child checkpoint namespace is present in the saver.
- Confirmed `git diff --check` passes and the protected dirty files are not included in
  the Task 2 staging set.

## Concerns and handoff

- Context7 was invoked as required but returned a monthly-quota-exhausted response.
  The implementation was checked against the installed LangGraph 1.2.9 APIs and the
  official LangGraph subgraph/runtime documentation instead.
- The whole repository suite is intentionally not a Task 2 completion gate because
  `run.py`, the legacy OAuth smoke, and compatibility tests still target the old sync
  API. The written plan assigns those changes and obsolete-adapter deletion to Task 3.
- No PR was opened; this is a durable Task 2 commit on the existing feature branch.
