# AGENTS.md — repository router

## Authority order

1. `GOAL.md` — product objective, gates, and experimental invariants.
2. `docs/architecture.md` — current runtime architecture and security boundaries.
3. `docs/stack.md` and `docs/controller.md` — component details.
4. `docs/plans/` — active executable work; it must not contradict the files above.

## Non-negotiable runtime rules

- **CHATGPT PRO OAUTH ONLY. NO OPENAI API KEY. NO RESPONSES API. NO CHAT COMPLETIONS API. NO OPENROUTER OR DEEPSEEK API FALLBACK.**
- Model authentication belongs to the official `openai-codex` SDK and its managed `codex app-server` login. Never read, copy, export, log, or commit its OAuth credentials; use only public SDK account metadata.
- LangGraph owns goal state, model turns, role routing, checkpoints, and completion evaluation.
- Both leader and follower explicitly configure the exact model ID `gpt-5.6-luna` on their official SDK threads.
- Models propose; `spine/controller.py` disposes and remains the sole movement-input writer.
- `spine/game_tools.py` is the bounded bridge between LangGraph and the existing launch, perception, controller, and trace modules.
- `episodes/`, `eval_set/`, and experiment ledgers are append-only.

## Commands

- `.venv\Scripts\python.exe spine\smoke_oauth_graph.py` — validate public managed-auth metadata, exact model catalog availability, both child graphs, role threads, schemas, and image input without game input.
- `.venv\Scripts\python.exe spine\run.py --goal "<completion condition>" --thread-id <id>` — create or resume a LangGraph goal.
- `.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py" -v` — run the suite.
- `.venv\Scripts\python.exe -m compileall -q spine` — compile check.
- `.venv\Scripts\python.exe spine\verify_perception.py` — perception evidence helper.

## Current work

- Follow `docs/superpowers/plans/2026-07-28-langgraph-codex-oauth-subagents.md` until the migration and bounded live vertical slice are complete.
- Preserve unrelated calibration captures and logs already present in the worktree.
- Record actual gate evidence in `status/gates.md`; tests or model prose do not prove a live game gate.

## When blocked

Write `status/BLOCKED.md` with the exact attempted operation, output, and required external change. A missing live-game capability does not justify restoring an API-backed model path.
