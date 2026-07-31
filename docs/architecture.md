# Runtime architecture

## Current decision

LangGraph is the agent runtime. The active model path uses the official
`openai-codex==0.144.4` Python SDK and its managed `codex app-server` process.
The app-server uses the existing ChatGPT-managed login. This path does **not**
use an OpenAI API key, OpenAI HTTP API, Responses API, Chat Completions API,
OpenRouter API, DeepSeek API, or an OpenAI-compatible endpoint.

The SDK/app-server owns authentication storage and refresh. Repository code
checks only the SDK's public account metadata and requires
`account.type == "chatgpt"` and `account.plan_type == "pro"`; it never opens, parses, copies, exports, prints, or
commits OAuth credential material.

Both temporary runtime roles are pinned to `gpt-5.6-luna`:

- leader: interprets the goal and observation, selects a high-level intent, and chooses level-up options;
- follower: sees the bounded observation/image and proposes one of `N NE E SE S SW W NW HOLD`.

This is a temporary model assignment. Changing it requires an explicit architecture update and evaluation; it must never happen through an undocumented environment-variable fallback.

## Ownership

```text
native /goal in Codex or Claude Code
              |
              v
LangGraph goal thread + SQLite checkpoints
  prepare -> observe -> leader -> follower -> bounded control -> observe
       |          |          |                       |
       |          +-> level-up selection             +-> controller/reflex veto
       +-> fixed-condition verification
              |
              v
deterministic evidence evaluator -> achieved | not_met | blocked
```

`spine/goal_graph.py` owns phase transitions and resumable state.
`spine/agent_subgraphs.py` owns the separately compiled `leader_agent` and
`follower_agent` child graphs. `spine/codex_sdk_client.py` owns the narrow
official-SDK invocation boundary and persistent role-to-Codex-thread bindings.
`spine/game_tools.py` owns the bridge into existing game capabilities.
`spine/controller.py` remains the sole movement-input writer.

LangGraph nodes never hold keys and never implement a real-time loop. A follower proposal is handed to the controller with measured latency. `control_window()` runs a short deterministic tick window, applies reflex veto/staleness/dither rules, records evidence, and neutralizes on exceptions.

## Authentication invariant

Runtime policy forbids these variables in the model process:

- `OPENAI_API_KEY`
- `OPENROUTER_API_KEY`
- `DEEPSEEK_API_KEY`

The compatibility helpers and direct SDK client reject them explicitly before
SDK startup. `CodexAgentClient.start()` requires the public SDK account
representation to report `type=chatgpt` and `plan_type=pro`, which is the
binding authentication check.

Every model invocation uses these official SDK/app-server controls:

- `model="gpt-5.6-luna"` on SDK thread start/resume for both roles;
- `Sandbox.read_only` and `ApprovalMode.deny_all`;
- app-server configuration disabling web search and the native shell tool;
- `output_schema` plus local JSON Schema validation;
- `TextInput` plus `LocalImageInput` for visual observations;
- persistent, distinct Codex thread IDs bound to leader and follower roles.

The public model catalog is separate evidence from turn output. The 2026-07-30
smoke confirmed `gpt-5.6-luna` is catalog-visible with text and image input.
The SDK `TurnResult` did not echo a model field, so no document or report may
describe the configured/catalog model as turn-response metadata.

## Goal semantics

The native `/goal` command is the operator-level persistence loop. The repository supplies the domain execution loop beneath it: a durable LangGraph `thread_id`, explicit goal text, retries, evidence references, and a structured result of `achieved`, `not_met`, or `blocked`.

The deterministic evaluator is authoritative for game claims. The host model may continue turns, delegate work, and summarize progress, but it cannot declare a survival target achieved without an `outcome.json` artifact satisfying the configured target and validity rules.

## Menu entry authority

Pre-run menus are vision-led. `SpineGameTools.prepare()` only launches or
attaches; it does not run an OCR menu macro. The LangGraph leader receives a
screenshot, proposes one bounded menu action (`menu_action`), and repeats
until the run starts. OCR may appear on observations as `ocr_hint` /
`screen_guess` but must not gate transitions. YOLO and the controller own
in-run movement safety. Use `--entry-only` to stop at the in-game HUD for G0
plumbing proofs.

**Display contract:** Vampire Survivors must be fullscreen on the capture
monitor at `capture_calibration_resolution`. `prepare()` fails closed if the
live frame size drifts. Run vision sessions unattended — desktop use causes
focus/size flicker and breaks the hit-test transform.

## Known incomplete live boundaries

- The six modifier values are explicit in `spine/config.yaml`, but a fresh live proof that the menu UI matches all six values is still required before a scored run.
- Attach/recovery from an already-running gameplay or level-up screen is implemented; live attach evidence still needs a gates.md append.
- The current upstream detector weights cover threats but not a proven gem/elite mapping.
- The real managed-OAuth no-game smoke passed through both actual child graphs,
  created distinct role Codex threads, returned schema-valid decisions, and
  attached `status/g0_capture.jpg` without emitting game input. This proves the
  model/graph/image boundary only. A live game action and G0 remain separate
  evidence and must not be inferred from this smoke.
