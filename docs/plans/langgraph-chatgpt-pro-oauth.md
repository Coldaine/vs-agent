# LangGraph ChatGPT Pro OAuth Runtime Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Status:** COMPLETE — live gameplay calibration remains a separate G0 gate

**Goal:** Replace the bespoke model-orchestration loop with a durable LangGraph goal runtime whose leader and follower both run as `gpt-5.6-luna` through the user's existing ChatGPT Pro OAuth login in the local Codex CLI.

**Architecture:** LangGraph owns goal state, phase transitions, checkpoints, leader/follower invocation, and completion evaluation. Existing `spine` modules remain the deterministic game boundary. A narrow subprocess adapter invokes `codex exec` with `--ignore-user-config`, `--ignore-rules`, `--ephemeral`, `--sandbox read-only`, and `--model gpt-5.6-luna`; Codex reads its existing ChatGPT OAuth session from `CODEX_HOME`, while the repository never reads, copies, logs, or stores OAuth credentials.

**Tech Stack:** Python 3.11+, LangGraph, SQLite checkpointing, Codex CLI 0.145.0+, ChatGPT Pro OAuth, `gpt-5.6-luna`, existing YOLO/OCR/controller stack.

## Global Constraints

- **CHATGPT PRO OAUTH ONLY. NO OPENAI API KEY. NO RESPONSES API. NO CHAT COMPLETIONS API.**
- **DO NOT read, copy, parse, export, log, or commit OAuth tokens.** Authentication remains exclusively owned by the installed Codex CLI and its existing `codex login` session.
- Both temporary roles use the exact model ID `gpt-5.6-luna`: leader and follower.
- The runtime must reject `OPENAI_API_KEY`, `OPENROUTER_API_KEY`, and `DEEPSEEK_API_KEY` for the LangGraph path so an API-backed fallback cannot happen silently.
- Models may propose only. `spine/controller.py` remains the sole writer of movement input, and every exit path neutralizes held input.
- The follower receives compact observations and emits one structured direction proposal; it does not get shell tools or arbitrary filesystem access.
- The leader receives compact state and emits a structured phase decision; it does not drive keys.
- `episodes/` and evaluation ledgers remain append-only.
- Existing untracked calibration captures and logs are user-owned and must not be added to framework commits.

---

### Task 1: ChatGPT Pro OAuth Codex adapter

**Files:**
- Create: `spine/oauth_codex.py`
- Create: `tests/test_oauth_codex.py`
- Modify: `requirements.txt`

**Interfaces:**
- Produces: `CodexOAuthConfig`, `CodexOAuthRunner.invoke(role, prompt, schema, image_path=None) -> dict`, `assert_oauth_only_environment()`.
- Consumes: installed `codex` executable and the existing ChatGPT OAuth session reported by `codex login status`.

- [x] **Step 1: Write failing tests** proving the default model is `gpt-5.6-luna`, both roles use the same model, forbidden API-key variables are rejected, and the subprocess command includes OAuth-safe flags without any bearer token or API endpoint.
- [x] **Step 2: Run** `.venv\Scripts\python.exe -m unittest discover -s tests -p "test_oauth_codex.py" -v` and verify failures are caused by the missing module.
- [x] **Step 3: Implement** a dependency-injected subprocess runner. Write JSON Schema and final-output files in a temporary directory, invoke `codex exec`, parse only the final JSON document, and delete the temporary directory automatically.
- [x] **Step 4: Run the focused tests** and verify all adapter tests pass.
- [x] **Step 5: Commit** with `git commit -m "feat: add ChatGPT OAuth Luna model adapter"`.

### Task 2: Durable LangGraph goal state and nodes

**Files:**
- Create: `spine/goal_graph.py`
- Create: `tests/test_goal_graph.py`
- Modify: `requirements.txt`

**Interfaces:**
- Produces: `GoalState`, `GoalStatus`, `build_goal_graph(model_runner, tools, checkpointer)`, and `run_goal(goal, thread_id, config) -> GoalStatus`.
- Consumes: `CodexOAuthRunner.invoke()` and a typed `GameTools` protocol.

- [x] **Step 1: Write failing tests** for `prepare -> verify -> lead -> follow -> observe -> evaluate`, `LEVEL_UP` routing, safety-fault neutralization, retry budget exhaustion, achieved termination, and checkpoint resume by `thread_id`.
- [x] **Step 2: Run** `.venv\Scripts\python.exe -m unittest discover -s tests -p "test_goal_graph.py" -v` and verify failures are caused by the missing graph module.
- [x] **Step 3: Implement** small graph nodes that exchange structured state only. The leader returns `{phase, intent, reason}`; the follower returns `{direction, confidence, reason}`; deterministic tool results decide transitions.
- [x] **Step 4: Run focused graph tests**, then all unit tests.
- [x] **Step 5: Commit** with `git commit -m "feat: add durable LangGraph goal runtime"`.

### Task 3: Bound existing game capabilities behind typed tools

**Files:**
- Create: `spine/game_tools.py`
- Create: `tests/test_game_tools.py`
- Modify: `spine/run.py`

**Interfaces:**
- Produces: `SpineGameTools.prepare()`, `observe()`, `submit_direction()`, `control_window()`, `select_level_up()`, `evaluate()`, and `neutralize()`.
- Consumes: `IOAdapter`, `Controller`, `perceive`, `launch`, and `EpisodeWriter`.

- [x] **Step 1: Write failing tests** proving model proposals cannot bypass `Controller`, control windows are time-bounded, invalid directions are rejected, and exceptions always neutralize input.
- [x] **Step 2: Run** `.venv\Scripts\python.exe -m unittest discover -s tests -p "test_game_tools.py" -v` and verify expected failures.
- [x] **Step 3: Implement** the adapter without duplicating capture, perception, input, or trace logic.
- [x] **Step 4: Make `--goal` the only model-driven entry path** in `spine/run.py`; the old API-backed orchestration path is removed rather than retained as a silent fallback.
- [x] **Step 5: Run focused and complete tests**, then commit with `git commit -m "feat: connect LangGraph to bounded game tools"`.

### Task 4: Authority and operator documentation

**Files:**
- Create: `docs/architecture.md`
- Modify: `AGENTS.md`
- Modify: `GOAL.md`
- Modify: `HANDOFF.md`
- Modify: `docs/stack.md`

**Interfaces:**
- Produces: one unambiguous source of truth for framework ownership, authentication, role boundaries, launch commands, and migration status.

- [x] **Step 1: Replace stale endpoint claims** with the explicit rule: **ChatGPT Pro OAuth via Codex CLI only; never an OpenAI API key or compatible HTTP endpoint for this LangGraph path.**
- [x] **Step 2: Document** LangGraph as orchestration runtime, `gpt-5.6-luna` as temporary leader and follower, and `spine/controller.py` as deterministic sole input writer.
- [x] **Step 3: Document operator commands** for OAuth preflight, unit tests, a no-game model smoke test, and a bounded live goal run.
- [x] **Step 4: Run an authority-flow pass** across `GOAL.md`, `docs/architecture.md`, `AGENTS.md`, `HANDOFF.md`, and this plan; remove contradictions.
- [x] **Step 5: Commit** with `git commit -m "docs: adopt LangGraph and ChatGPT Pro OAuth runtime"`.

### Task 5: Verification and migration evidence

**Files:**
- Modify: `docs/plans/langgraph-chatgpt-pro-oauth.md`
- Modify: `status/gates.md` only if a live game gate is actually proven.

**Interfaces:**
- Consumes: installed Codex OAuth session, test suite, LangGraph graph, and optional live game process.
- Produces: reproducible proof without recording credentials or treating a model response as gameplay proof.

- [x] **Step 1: Run OAuth preflight:** `codex login status` reported `Logged in using ChatGPT`.
- [x] **Step 2: Run exact-model smoke:** `gpt-5.6-luna` returned the required marker through `codex exec` and ChatGPT OAuth.
- [x] **Step 3: Run** `.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py" -v` and `.venv\Scripts\python.exe -m compileall -q spine`; 38 tests pass and compilation is clean.
- [x] **Step 4: Run a graph smoke with fake game tools but the real OAuth leader and follower**; both `gpt-5.6-luna` roles completed and the deterministic evaluator returned `achieved` with `smoke-control` and `smoke-outcome` evidence. A separate real-image OAuth smoke attached the saved gameplay HUD frame; the follower correctly returned `HOLD` because a level-up screen was active.
- [x] **Step 5: Keep the live control-window smoke unclaimed.** The game is not safely attachable yet, and the six modifier states still need live UI verification. These remain G0 work documented in `docs/architecture.md` and are not inferred from framework tests.
- [x] **Step 6: Mark the framework/OAuth plan complete after promoting lasting facts into `docs/architecture.md`.** Keep this requested plan artifact through user review; delete it in a later accepted cleanup rather than during the delivery commit.
- [x] **Step 7: Push the branch** after validation so the durable work is preserved remotely. The implementation is on `origin/pr/rename-pilot-planner`; no pull request was opened automatically.
