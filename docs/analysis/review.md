# Capability Audit and Refactor Plan

This is an honest, evidence-cited capability audit and refactor plan for the Vampire Survivors self-improving agent system.

## Capability Audit

### 1. Auth Integrity
- **Status:** **PASSED & PROTECTED**
- **Evidence:** 
  - Verified that [vs-agent/spine/codex_sdk_client.py](vs-agent/spine/codex_sdk_client.py) wraps the official `openai-codex` SDK and enforces managed OAuth-only authentication, failing closed if non-ChatGPT authentication is detected in [vs-agent/spine/codex_sdk_client.py](vs-agent/spine/codex_sdk_client.py#L90-L95).
  - Explicit checks in [vs-agent/spine/model_client.py](vs-agent/spine/model_client.py#L32-L46) actively prevent leaking of forbidden `OPENAI_API_KEY`, `OPENROUTER_API_KEY`, or `DEEPSEEK_API_KEY` keys, throwing a `RuntimeError` if any are present in the environment block.
  - The model `gpt-5.6-luna` is pinned of role threads in [vs-agent/spine/codex_sdk_client.py](vs-agent/spine/codex_sdk_client.py#L25).
  - Telemetry logging in [vs-agent/spine/model_client.py](vs-agent/spine/model_client.py#L106-L116) formats records cleanly inside the append-only model calls log without tracking secret context.

### 2. Controller is Sole Input Writer
- **Status:** **PASSED & PROTECTED**
- **Evidence:**
  - [vs-agent/spine/controller.py](vs-agent/spine/controller.py) owns the sole authority over sending movement directional controls via the controller instance's gamepad/keyboard adapter inputs.
  - Every model-based proposal maps to `submit_follower_proposal` in [vs-agent/spine/controller.py](vs-agent/spine/controller.py#L22) which regulates dither, staleness, and YOLO veto boundaries before committing any actual keys or stick values.
  - Robust exception handlers in [vs-agent/spine/game_tools.py](vs-agent/spine/game_tools.py#L214) and [vs-agent/spine/game_tools.py](vs-agent/spine/game_tools.py#L251) ensure that any failures on observation, perception, or decision execution neutralize active inputs and fail closed.

### 3. Dead Code / Duplicate Model Paths (Naming Drift)
- **Status:** **MUST-FIX**
- **Finding:** A dual model-path system coexists in the codebase.
  - Direct SDK queries are run via [vs-agent/spine/agent_subgraphs.py](vs-agent/spine/agent_subgraphs.py) and [vs-agent/spine/goal_graph.py](vs-agent/spine/goal_graph.py) using the correct `leader` and `follower` role bindings.
  - However, offline and labeling utility scripts ([vs-agent/spine/label_eval.py](vs-agent/spine/label_eval.py#L27-L28), [vs-agent/spine/replay_eval.py](vs-agent/spine/replay_eval.py#L29), and [vs-agent/spine/review.py](vs-agent/spine/review.py#L66)) continue to import and route requests through [vs-agent/spine/model_client.py](vs-agent/spine/model_client.py) using the older `call_pilot`, `call_pilot_eval`, and `call_planner` syntax.
  - This naming mismatch propagates across logged model function strings (`call_pilot` and `call_planner` instead of `leader` and `follower`) and creates unnecessary maintenance overhead.
  - The legacysubprocess runner file `spine/oauth_codex.py` and its tests have been deleted, but documentation continues to reference them, causing confusion.

### 4. Menu Entry Correctness
- **Status:** **SHOULD-FIX**
- **Finding:** 
  - Vision-led menu entry is fully integrated into the parent graph, where [vs-agent/spine/goal_graph.py](vs-agent/spine/goal_graph.py#L190-L215) queries the leader graph for screen classification and next action.
  - Bounded verification relies on correct classifier mapping in [vs-agent/spine/launch.py](vs-agent/spine/launch.py#L32), verifying whether the OCR text contains characters or stage criteria before allowing confirmations.
  - The menu search limits are guarded by focus checks in [vs-agent/spine/launch.py](vs-agent/spine/launch.py#L195), ensuring OCR results act solely as advisory hints while the controller uses fixed coordinate hit-testing.

### 5. Capture/Calibration
- **Status:** **PASSED & PROTECTED**
- **Finding:**
  - Fully consistent across [vs-agent/spine/config.yaml](vs-agent/spine/config.yaml), [vs-agent/spine/io_adapter.py](vs-agent/spine/io_adapter.py), and [vs-agent/spine/capture_transform.py](vs-agent/spine/capture_transform.py).
  - The calibrated `capture_to_input_scale` (1.25x) and fixed `capture_calibration_resolution` ([2560, 1440]) are correctly applied to WGC frame coordinates to map click frames to hit-tests.
  - Fullscreen constraints are actively verified by [vs-agent/spine/capture_transform.py](vs-agent/spine/capture_transform.py#L51) on initialization, preventing aspect ratio and coordinate translation drifting during window resizing.

### 6. Gate Evidence vs. Claims
- **Status:** **PASSED & PROTECTED**
- **Finding:**
  - No gates are claimed as passed without live proof. [vs-agent/status/gates.md](vs-agent/status/gates.md#L5-L15) explicitly lists G0 as **IN PROGRESS**, citing a calibration run where Hurry and Limit Break were enabled. No shortcuts or fabricated assertions are present in the verification history.

### 7. Test Quality
- **Status:** **SHOULD-FIX**
- **Finding:**
  - The 81 unit tests in [vs-agent/tests/](vs-agent/tests/) are excellent and maintain a solid floor for verifying auth Lifecycle, graph checkpoints, and coordinate conversion.
  - However, they use mocks to duplicate the official SDK interface and do not verify the actual live gameplay environment. 
  - There are zero skipped or disabled tests, confirming that no test coverage regression is being hidden.

### 8. Security/Secrets Hygiene
- **Status:** **PASSED & PROTECTED**
- **Finding:**
  - No secret variables, `.env` files, or local keys are present or committed in the repository.
  - File exclusions in [vs-agent/.gitignore](vs-agent/.gitignore) correctly prevent tracking `.env` files and virtual environments, keeping the OAuth model client clean.

### 9. Docs Consistency
- **Status:** **MUST-FIX**
- **Finding:**
  - There is a narrative drift across documents regarding the model runner.
  - [vs-agent/docs/plans/langgraph-chatgpt-pro-oauth.md](vs-agent/docs/plans/langgraph-chatgpt-pro-oauth.md#L15) continues to reference the temporary subprocess subprocess wrapper `codex exec` and the obsolete `spine/oauth_codex.py` adapter.
  - Meanwhile, [vs-agent/docs/superpowers/plans/2026-07-28-langgraph-codex-oauth-subagents.md](vs-agent/docs/superpowers/plans/2026-07-28-langgraph-codex-oauth-subagents.md#L5) asserts the official `openai-codex` SDK python library integration. Documentation must tell a single, reconciled story.

### 10. Loop Readiness
- **Status:** **SHOULD-FIX**
- **Finding:**
  - The core modules for offline scoring [vs-agent/spine/replay_eval.py](vs-agent/spine/replay_eval.py) and evaluation parsing [vs-agent/spine/label_eval.py](vs-agent/spine/label_eval.py) are present.
  - However, our detector weights mapping in [vs-agent/spine/config.yaml](vs-agent/spine/config.yaml#L95) contains only threat tracking: `monster: enemy`. Gem/elite label-mapping remains incomplete on the actual detector. We need to implement a fallback logic or specify how labels are processed prior to running the training self-improvement loop (Loop P).

---

## Refactor Plan

We recommend the following sequence of high-value refactors to eliminate naming and model path drift, align document stories, and harden the G0 vertical slice:

1. **Unify Runtime Naming:** Replace all remaining occurrences of `pilot` and `planner` with `follower` and `leader` respectively. This includes modifying [vs-agent/spine/model_client.py](vs-agent/spine/model_client.py), [vs-agent/spine/replay_eval.py](vs-agent/spine/replay_eval.py), [vs-agent/spine/label_eval.py](vs-agent/spine/label_eval.py), and [vs-agent/spine/review.py](vs-agent/spine/review.py).
2. **Quarantine / Deprecate Model Client:** Ensure [vs-agent/spine/model_client.py](vs-agent/spine/model_client.py)'s public functions strictly assert the OAuth environment, match leader/follower naming conventions, and format model calls correctly as `call_leader` and `call_follower` in telemetry.
3. **Reconcile Documentation:** Update [vs-agent/docs/plans/langgraph-chatgpt-pro-oauth.md](vs-agent/docs/plans/langgraph-chatgpt-pro-oauth.md) to officially deprecate the old subprocess design and point to the `openai-codex` SDK implementation.
4. **Harden G0 Verification Pipeline:** Prepare [vs-agent/spine/verify_g0.py](vs-agent/spine/verify_g0.py) to run cleanly under fixed fullscreen bounds once the human prerequisites are completed.
