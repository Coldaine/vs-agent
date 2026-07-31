# LangGraph Codex OAuth Subagents Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the invented one-shot `codex exec` model wrapper with real LangGraph leader/follower subgraphs backed by the official Python Codex SDK and Codex-managed ChatGPT OAuth, then prove a bounded live game action.

**Architecture:** A deterministic parent `StateGraph` routes separately compiled leader and follower child graphs. One process-lifetime `AsyncCodex` client owns app-server and OAuth; each role reuses its own Codex thread. Deterministic game tools validate proposals and remain the only input writers.

**Tech Stack:** Python 3.13, LangGraph 1.2.9, `openai-codex==0.144.4`, Codex app-server, ChatGPT managed OAuth, SQLite checkpoints, existing controller/perception stack.

## Global Constraints

- Never read, copy, log, export, or commit OAuth token material.
- Never use an API key or direct OpenAI HTTP client for this runtime.
- Use the official `openai-codex==0.144.4` SDK with its pinned CLI runtime by default.
- Keep one `AsyncCodex` instance alive for the runtime process and close it deterministically.
- Leader and follower must be separately compiled LangGraph child graphs with narrow state schemas.
- Codex children get no game tools; `SpineGameTools` and `Controller` remain the sole input boundary.
- Every exception or ambiguous physical state neutralizes input and fails closed.
- Preserve the G0 harness work committed in `9acf694`; do not replace it with screenshots or fake-game evidence.

---

### Task 1: Official Codex SDK OAuth client

**Files:**
- Create: `spine/codex_sdk_client.py`
- Create: `tests/test_codex_sdk_client.py`
- Modify: `requirements.txt`

**Interfaces:**
- Produces: `CodexAgentClient.start()`, `close()`, and `invoke(role, prompt, schema, image_path=None, thread_id=None) -> CodexInvocation`.
- Produces: `CodexInvocation(payload: dict, thread_id: str, turn_id: str, usage: dict | None)`.
- Consumes: public `AsyncCodex.account`, `thread_start`, `thread_resume`, `LocalImageInput`, `Sandbox.read_only`, and `ApprovalMode.deny_all` APIs.

- [ ] **Step 1: Add failing lifecycle and auth tests** proving one SDK client is entered once, account metadata must report ChatGPT-managed auth, role threads are started/resumed, images use `LocalImageInput`, invalid JSON is rejected, and close exits the SDK once.
- [ ] **Step 2: Run** `.venv\Scripts\python.exe -m unittest tests.test_codex_sdk_client -v` and verify failure is caused by the missing module.
- [ ] **Step 3: Implement the minimal async client** with dependency-injected SDK factories. Configure read-only sandbox, deny-all approval, disabled web search, and disabled native shell. Parse and validate `final_response`; do not expose authentication material.
- [ ] **Step 4: Add `openai-codex==0.144.4`** to `requirements.txt`, install it, and run `pip check`.
- [ ] **Step 5: Run the focused tests** and commit `feat: add official Codex SDK OAuth client`.

### Task 2: Real LangGraph leader and follower subgraphs

**Files:**
- Create: `spine/agent_subgraphs.py`
- Create: `tests/test_agent_subgraphs.py`
- Modify: `spine/goal_graph.py`
- Modify: `tests/test_goal_graph.py`

**Interfaces:**
- Produces: `build_leader_subgraph()` and `build_follower_subgraph()` compiled child graphs.
- Produces: `AgentRuntime(codex: CodexAgentClient, tools: GameTools)` supplied through LangGraph runtime context.
- Consumes: Task 1 `CodexAgentClient.invoke` and existing leader/follower JSON Schemas.

- [ ] **Step 1: Write failing child-graph tests** proving separate compiled graphs, disjoint input/output schemas, role-correct SDK invocation, thread-ID reuse, image forwarding, and no game tool access.
- [ ] **Step 2: Run** `.venv\Scripts\python.exe -m unittest tests.test_agent_subgraphs -v` and verify the missing subgraph module is the failure.
- [ ] **Step 3: Implement each role as a child `StateGraph`** with prompt construction and model invocation in child nodes. Compile with inherited per-invocation checkpointing.
- [ ] **Step 4: Replace monolithic model closures in the parent graph** with explicit wrapper nodes that map parent state into each compiled child and map only validated results back.
- [ ] **Step 5: Extend checkpoint tests** to inspect child namespaces and prove parent resume does not repeat already completed child work.
- [ ] **Step 6: Run focused graph tests** and commit `feat: add LangGraph leader follower subgraphs`.

### Task 3: Runtime wiring and removal of the invalid adapter

**Files:**
- Modify: `spine/run.py`
- Modify: `spine/model_client.py`
- Modify: `spine/smoke_oauth_graph.py`
- Modify: `tests/test_run_goal.py`
- Modify: `tests/test_model_client_oauth.py`
- Delete: `spine/oauth_codex.py`
- Delete: `tests/test_oauth_codex.py`
- Delete: `tests/test_oauth_graph_smoke.py`

**Interfaces:**
- Consumes: `CodexAgentClient`, `AgentRuntime`, and the parent graph from Tasks 1-2.
- Produces: one runtime lifecycle that starts SDK, checks account metadata, runs/resumes LangGraph, and always closes SDK and neutralizes tools.

- [ ] **Step 1: Write failing runtime tests** proving one SDK lifecycle spans the whole goal, leader/follower thread IDs survive graph checkpoints, and shutdown neutralizes input on success and failure.
- [ ] **Step 2: Rewire `run.py` and compatibility callers** to the official client and async graph execution without nested event-loop calls.
- [ ] **Step 3: Replace the old smoke** with an SDK-backed two-child no-game smoke; preserve fake game tools only as the deterministic boundary.
- [ ] **Step 4: Delete the one-shot adapter and obsolete tests**, then run `rg -n "CodexOAuthRunner|codex exec|oauth_codex" spine tests` and require no active runtime matches.
- [ ] **Step 5: Run the complete unit suite and `pip check`**, then commit `refactor: run LangGraph agents through Codex SDK`.

### Task 4: Real OAuth, structured-output, and image verification

**Files:**
- Modify: `spine/smoke_oauth_graph.py`
- Create: `tests/test_real_oauth_smoke_contract.py`
- Modify: `docs/architecture.md`
- Modify: `docs/stack.md`
- Modify: `HANDOFF.md`
- Modify: `GOAL.md`

**Interfaces:**
- Consumes: installed official SDK, existing managed ChatGPT login, saved local gameplay image, and no-input fake game tools.
- Produces: machine-readable smoke result containing auth mode, parent LangGraph thread ID, distinct child graph names, persistent Codex role thread IDs, model IDs, and structured decisions.

- [ ] **Step 1: Add a smoke-contract test** that rejects results lacking ChatGPT auth metadata, both child roles, role thread IDs, or schema-valid payloads.
- [ ] **Step 2: Run the real no-game smoke** and require both child subgraphs to complete through the official SDK using the existing login.
- [ ] **Step 3: Run a real image turn** through one child using a saved gameplay frame and require schema-valid output.
- [ ] **Step 4: Rewrite authority docs** to cite the official SDK/app-server path and remove every claim that `codex exec` is a LangGraph model integration.
- [ ] **Step 5: Run the full suite, compile check, `pip check`, and documentation searches**, then commit `docs: record official SDK OAuth subagent verification`.

### Task 5: Bounded live vertical slice and G0 completion

**Files:**
- Modify: `docs/plans/g0-live-followup.md`
- Modify: `status/gates.md`
- Modify: `status/BLOCKED.md`
- Modify only if a proven defect is found: `spine/game_tools.py`, `spine/controller.py`, `spine/io_adapter.py`, `spine/launch.py`, `spine/verify_g0.py`
- Test only if implementation changes: corresponding `tests/test_*.py`

**Interfaces:**
- Consumes: official OAuth client, parent graph, child subgraphs, and deterministic G0 harness.
- Produces: live proof of OAuth -> leader/follower child -> one validated game action -> re-observation -> neutralization, followed by all explicit G0 gates.

- [ ] **Step 1: Run entry-only mode** from a known menu state and require the parent graph to reach the in-game HUD through the leader child without bypassing modifier/character/stage guards.
- [ ] **Step 2: Run one two-second movement window** and require the follower child proposal to pass controller validation, produce a changed observation, and end with neutral input.
- [ ] **Step 3: Verify attach recovery and all six modifiers** using the live verifier; treat unknown or indirect evidence as failure.
- [ ] **Step 4: Fix only defects exposed by the live slice**, adding a failing regression test before each implementation change and re-running the bounded slice afterward.
- [ ] **Step 5: Run the full completion audit** against every G0 stop condition in `GOAL.md`; update status documents with commands and outcomes, not accumulated screenshots.
- [ ] **Step 6: Commit the verified live result**, push the branch, self-review the full diff, and open a non-draft PR only if the entire requested scope is complete.
