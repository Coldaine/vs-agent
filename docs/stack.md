# Current stack

| Layer | Implementation | Authority |
|---|---|---|
| Goal runtime | LangGraph 1.2.x | phases, routing, checkpoints, resume |
| Checkpoints | `langgraph-checkpoint-sqlite` | durable local goal state |
| Authentication | existing Codex CLI ChatGPT Pro OAuth session | OAuth storage and refresh |
| Leader model | `gpt-5.6-luna` via `codex exec` | intent and level-up proposal |
| Follower model | `gpt-5.6-luna` via `codex exec` | one movement proposal |
| Model adapter | `spine/oauth_codex.py` | structured OAuth-only invocation |
| Game bridge | `spine/game_tools.py` | bounded operations and evidence |
| Controller | `spine/controller.py` | sole movement-input writer |
| Reflex | `spine/reflex.py` plus YOLO detections | deterministic safety veto |
| Capture/input | `spine/io_adapter.py` | WGC/DXCam and keyboard/gamepad boundary |
| Perception | `spine/perceive.py` | YOLO/OCR state |
| Trace | `spine/trace.py` | append-only episode evidence |

## Authentication: critically not API

The model runtime uses **ChatGPT Pro OAuth, not the OpenAI API**. It does not accept an API base URL or provider key. It does not use OpenRouter or DeepSeek. It does not read the OAuth credential. The installed Codex CLI is already logged in to ChatGPT and is the only component allowed to own that authentication state.

The LangGraph path deliberately rejects populated `OPENAI_API_KEY`, `OPENROUTER_API_KEY`, and `DEEPSEEK_API_KEY` variables. This is a fail-closed guarantee against accidentally billing or routing through an API when the requested authentication is the user's ChatGPT Pro OAuth subscription.

## Why LangGraph

LangGraph supplies durable state transitions, checkpoint/resume, explicit branch routing, bounded retries, and a clean place to separate model decisions from deterministic evidence. It does not replace the controller or turn the LLM into a real-time key loop.

## Runtime command

```powershell
codex login status
.venv\Scripts\python.exe spine\smoke_oauth_graph.py
.venv\Scripts\python.exe spine\run.py `
  --goal "Complete a fixed-condition run and prove survival reached 540 seconds" `
  --thread-id goal-g4
```

Expected authentication preflight: `Logged in using ChatGPT`. Do not wrap this command in Doppler and do not inject any API key.

## Current model assignment

Both leader and follower use `gpt-5.6-luna` for the migration. The follower is intentionally not expected to maintain a 2 Hz network/model cadence. It proposes an intent/direction, while `SpineGameTools.control_window()` and `Controller` handle a bounded deterministic tick window. Latency is measured and passed into controller staleness handling.

The eventual optimized follower may be a smaller local or distilled model, but that is not the current runtime and must not be substituted silently.
