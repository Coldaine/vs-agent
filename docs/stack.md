# Current stack

| Layer | Implementation | Authority |
|---|---|---|
| Goal runtime | LangGraph 1.2.x | phases, routing, checkpoints, resume |
| Checkpoints | `langgraph-checkpoint-sqlite` | durable local goal state |
| Authentication | official `openai-codex` SDK + managed `codex app-server` ChatGPT login | auth storage and refresh |
| Leader model | explicitly configured `gpt-5.6-luna` SDK thread | intent and level-up proposal |
| Follower model | explicitly configured `gpt-5.6-luna` SDK thread | one movement proposal |
| Model adapter | `spine/codex_sdk_client.py` | SDK lifecycle, role threads, images, schema validation |
| Game bridge | `spine/game_tools.py` | bounded operations and evidence |
| Controller | `spine/controller.py` | sole movement-input writer |
| Reflex | `spine/reflex.py` plus YOLO detections | deterministic safety veto |
| Capture/input | `spine/io_adapter.py` | WGC/DXCam and keyboard/gamepad boundary |
| Perception | `spine/perceive.py` | YOLO/OCR state |
| Trace | `spine/trace.py` | append-only episode evidence |

## Authentication: critically not API

The model runtime uses the official SDK's **ChatGPT-managed login, not the
OpenAI API**. It does not accept an API base URL or provider key and does not
use OpenRouter or DeepSeek. The SDK/app-server owns authentication state;
repository code reads only public account metadata and never reads the OAuth
credential.

Runtime policy forbids `OPENAI_API_KEY`, `OPENROUTER_API_KEY`, and
`DEEPSEEK_API_KEY`. Compatibility helpers reject populated values explicitly;
the direct LangGraph path binds authentication by accepting only public SDK
account metadata with `type=chatgpt`.

## Why LangGraph

LangGraph supplies durable state transitions, checkpoint/resume, explicit branch routing, bounded retries, and a clean place to separate model decisions from deterministic evidence. It does not replace the controller or turn the LLM into a real-time key loop.

## Runtime command

```powershell
.venv\Scripts\python.exe spine\smoke_oauth_graph.py
.venv\Scripts\python.exe spine\run.py `
  --goal "Complete a fixed-condition run and prove survival reached 540 seconds" `
  --thread-id goal-g4
```

The smoke itself validates public SDK account metadata, exact model-catalog
availability, both child graphs, distinct role threads, structured decisions,
and the image attachment. Do not wrap it in Doppler or inject any API key.

## Current model assignment

Both leader and follower role threads explicitly configure `gpt-5.6-luna` on
start/resume. Public catalog availability is checked separately; the
SDK `TurnResult` does not echo the model. The follower is intentionally not
expected to maintain a 2 Hz network/model cadence. It proposes an
intent/direction, while `SpineGameTools.control_window()` and `Controller`
handle a bounded deterministic tick window.

The eventual optimized follower may be a smaller local or distilled model, but that is not the current runtime and must not be substituted silently.
