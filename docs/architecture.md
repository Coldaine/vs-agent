# Runtime architecture

## Current decision

LangGraph is the agent runtime. The active model path uses **ChatGPT Pro OAuth through the locally authenticated Codex CLI only**. It does **not** use an OpenAI API key, OpenAI HTTP API, Responses API, Chat Completions API, OpenRouter API, DeepSeek API, or an OpenAI-compatible endpoint.

The installed Codex CLI owns OAuth storage and refresh. Repository code may execute `codex login status` and `codex exec`; it must never open, parse, copy, export, print, or commit the OAuth credential material itself.

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

`spine/goal_graph.py` owns phase transitions and resumable state. `spine/oauth_codex.py` owns structured model invocation. `spine/game_tools.py` owns the narrow bridge into existing game capabilities. `spine/controller.py` remains the sole movement-input writer. `spine/io_adapter.py`, `spine/launch.py`, `spine/perceive.py`, and `spine/trace.py` retain their existing responsibilities.

LangGraph nodes never hold keys and never implement a real-time loop. A follower proposal is handed to the controller with measured latency. `control_window()` runs a short deterministic tick window, applies reflex veto/staleness/dither rules, records evidence, and neutralizes on exceptions.

## Authentication invariant

The LangGraph process fails closed if any of these variables are populated:

- `OPENAI_API_KEY`
- `OPENROUTER_API_KEY`
- `DEEPSEEK_API_KEY`

This prevents a configured shell, Doppler wrapper, or inherited environment from silently changing the requested ChatGPT Pro OAuth path into an API-billed path. `CodexOAuthRunner` additionally requires `codex login status` to contain `Logged in using ChatGPT`.

Every model invocation uses these Codex controls:

- `--ignore-user-config` and `--ignore-rules` to avoid unrelated project/provider behavior;
- `--ephemeral` so role calls do not create reusable Codex conversations;
- `--sandbox read-only` and an empty temporary working directory;
- `--model gpt-5.6-luna` for both leader and follower;
- `--output-schema` for constrained JSON output;
- `--image <path>` for follower/leader visual observations;
- JSON event inspection that rejects observed tool activity.

## Goal semantics

The native `/goal` command is the operator-level persistence loop. The repository supplies the domain execution loop beneath it: a durable LangGraph `thread_id`, explicit goal text, retries, evidence references, and a structured result of `achieved`, `not_met`, or `blocked`.

The deterministic evaluator is authoritative for game claims. The host model may continue turns, delegate work, and summarize progress, but it cannot declare a survival target achieved without an `outcome.json` artifact satisfying the configured target and validity rules.

## Known incomplete live boundaries

- The six modifier values are explicit in `spine/config.yaml`, but a fresh live proof that the menu UI matches all six values is still required before a scored run.
- Attach/recovery from an already-running gameplay or level-up screen remains incomplete.
- The current upstream detector weights cover threats but not a proven gem/elite mapping.
- A real OAuth leader/follower graph smoke is required after unit tests; a live game smoke is separate evidence and must not be inferred from it.
