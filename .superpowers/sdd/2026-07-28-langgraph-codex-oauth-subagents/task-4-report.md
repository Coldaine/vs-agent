# Task 4 report: real managed OAuth, structured output, and image verification

Date: 2026-07-30

## Status

Implemented and live-verified. This is a no-game model/graph/image proof, not a
live game-action proof and not G0 completion.

## Test-first contract

`tests/test_real_oauth_smoke_contract.py` was added before the producer change.
The initial focused run failed exactly because
`validate_smoke_result` did not exist. The completed contract rejects missing
or non-ChatGPT public auth metadata, missing/wrong child roles, missing or
duplicate role thread IDs, invalid leader/follower payloads, a missing image
attachment, an incorrect configured model or catalog modality, missing turn
IDs, or any claimed game input emission.

## First real run: exact sanitized failure

Command:

```powershell
.venv\Scripts\python.exe spine\smoke_oauth_graph.py
```

The first real run entered the parent graph and actual `leader_agent`, then
failed at the official SDK input-normalization boundary. No token file or token
value was inspected.

```text
TypeError: unsupported input item: <class 'str'>
During task with name 'invoke_codex_leader' and id '702f2aed-b39a-1896-b960-f56f22238d14'
During task with name 'leader' and id 'dc8d7c90-c7f4-9461-4ec0-186a41ac523e'
```

Root cause: `CodexAgentClient` built a mixed image input as
`[str, LocalImageInput]`; SDK 0.144.4 requires public input objects in a mixed
list. A focused regression test was observed failing, then the client was
changed to `[TextInput(prompt), LocalImageInput(path)]` and the focused SDK
tests passed.

## Successful real retry: exact sanitized output

The unchanged real command then exited 0 in 34.1 seconds and printed this
machine-readable record:

```json
{"account": {"plan_type": "pro", "type": "chatgpt"}, "contract_version": 1, "game_input": {"emitted": false}, "image": {"attached": true, "role": "leader", "schema_valid": true, "source": "status/g0_capture.jpg"}, "langgraph": {"child_graphs": ["leader_agent", "follower_agent"], "parent_thread_id": "oauth-smoke"}, "model": {"catalog_available": true, "catalog_input_modalities": ["text", "image"], "configured": "gpt-5.6-luna", "turn_result_echoed_model": false}, "roles": {"follower": {"codex_thread_id": "019fb63f-5057-7003-bd45-da338d32385d", "decision": {"confidence": 0.99, "direction": "HOLD", "reason": "The observation is a synthetic safe play state, but the screenshot shows the character-selection menu rather than active gameplay; no movement is warranted."}, "graph_name": "follower_agent", "schema_valid": true, "turn_id": "019fb63f-6438-7b92-94fd-49abea496856"}, "leader": {"codex_thread_id": "019fb63f-0cdb-74f2-8d8c-5d4a1213e495", "decision": {"intent": "Select Antonio, choose Mad Forest, clear all modifiers, and confirm the fixed smoke-test contract before starting the run.", "option": null, "reason": "The screenshot shows character selection with Imelda currently selected and The Bone Zone checked; this is not a LEVEL_UP screen."}, "graph_name": "leader_agent", "schema_valid": true, "turn_id": "019fb63f-2107-7d81-aff4-de00816eb53c"}}, "status": "achieved"}
```

## Evidence boundaries

- Authentication proof is limited to public SDK fields:
  `account.type=chatgpt` and `account.plan_type=pro`. Email was not recorded;
  OAuth token files were not opened.
- Model proof has two independent parts: the client explicitly configured
  `gpt-5.6-luna` on each SDK thread, and the public catalog listed that ID with
  text and image input. `TurnResult` did **not** expose a model field, so the
  report does not attribute the model ID to turn-response metadata.
- Parent workflow proof is LangGraph thread `oauth-smoke`.
- Role proof is completion through separately compiled `leader_agent` and
  `follower_agent` graphs with distinct persisted Codex thread IDs and locally
  JSON-Schema-valid decisions.
- Image proof is a real `LocalImageInput` using the existing read-only
  `status/g0_capture.jpg`. The image was neither overwritten nor staged.
- The fake game boundary accepted the validated proposal but contains no OS or
  game input writer; the result records `game_input.emitted=false`.
- The screenshot depicts a character-selection state. The role decisions are
  evidence that image perception and schemas worked, not that gameplay, a
  live controller action, or G0 succeeded.

## Final verification

```text
.venv\Scripts\python.exe -m pytest tests -q
81 passed, 21 subtests passed in 2.84s

.venv\Scripts\python.exe -m unittest discover -s tests -p 'test_*.py' -v
Ran 81 tests in 1.996s
OK

.venv\Scripts\python.exe -m pip check
No broken requirements found.

.venv\Scripts\python.exe -m compileall -q spine tests
exit 0

git diff --check
exit 0

rg active authority docs for codex exec / deleted adapter / CLI-only preflight
NO_MATCHES

rg spine tests for CodexOAuthRunner / codex exec / oauth_codex
NO_MATCHES
```

The final fresh real smoke, after all code and documentation changes, exited 0
in 34.7 seconds with this exact sanitized output:

```json
{"account": {"plan_type": "pro", "type": "chatgpt"}, "contract_version": 1, "game_input": {"emitted": false}, "image": {"attached": true, "role": "leader", "schema_valid": true, "source": "status/g0_capture.jpg"}, "langgraph": {"child_graphs": ["leader_agent", "follower_agent"], "parent_thread_id": "oauth-smoke"}, "model": {"catalog_available": true, "catalog_input_modalities": ["text", "image"], "configured": "gpt-5.6-luna", "turn_result_echoed_model": false}, "roles": {"follower": {"codex_thread_id": "019fb646-364b-7532-9398-077e869099d0", "decision": {"confidence": 0.98, "direction": "W", "reason": "Antonio is immediately left of the currently selected Imelda; move left toward the required character."}, "graph_name": "follower_agent", "schema_valid": true, "turn_id": "019fb646-4a6e-70c0-888a-3d5f8fb5fd15"}, "leader": {"codex_thread_id": "019fb645-f736-7d60-a707-6ec215d79878", "decision": {"intent": "enforce_eval_contract", "option": null, "reason": "The screenshot shows Imelda selected and The Bone Zone checked, so the required contract (Antonio, Mad Forest, no modifiers) is not yet satisfied."}, "graph_name": "leader_agent", "schema_valid": true, "turn_id": "019fb646-0b88-7cb0-a4d9-50e6f6fe85ab"}}, "status": "achieved"}
```
