# AGENTS.md — repository router

## Authority order

1. `GOAL.md` — product objective, gates, and experimental invariants.
2. `docs/architecture.md` — current runtime architecture and security boundaries.
3. `docs/stack.md` and `docs/controller.md` — component details.
4. `docs/plans/` — active executable work; it must not contradict the files above.

## Non-negotiable runtime rules

- **CHATGPT PRO OAUTH ONLY. NO OPENAI API KEY. NO RESPONSES API. NO CHAT COMPLETIONS API. NO OPENROUTER OR DEEPSEEK API FALLBACK.**
- Model authentication belongs to the installed Codex CLI and its existing `codex login` session. Never read, copy, export, log, or commit its OAuth credentials.
- LangGraph owns goal state, model turns, role routing, checkpoints, and completion evaluation.
- For the current migration, both leader and follower use the exact model ID `gpt-5.6-luna` through `codex exec`.
- Models propose; `spine/controller.py` disposes and remains the sole movement-input writer.
- `spine/game_tools.py` is the bounded bridge between LangGraph and the existing launch, perception, controller, and trace modules.
- `episodes/`, `eval_set/`, and experiment ledgers are append-only.

## Commands

- `codex login status` — must report `Logged in using ChatGPT`.
- `.venv\Scripts\python.exe spine\run.py --goal "<completion condition>" --thread-id <id>` — create or resume a LangGraph goal.
- `.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py" -v` — run the suite.
- `.venv\Scripts\python.exe -m compileall -q spine` — compile check.
- `.venv\Scripts\python.exe spine\verify_perception.py` — perception evidence helper.

## Current work

- Follow `docs/plans/langgraph-chatgpt-pro-oauth.md` until the migration is complete.
- Preserve unrelated calibration captures and logs already present in the worktree.
- Record actual gate evidence in `status/gates.md`; tests or model prose do not prove a live game gate.

## When blocked

Write `status/BLOCKED.md` with the exact attempted operation, output, and required external change. A missing live-game capability does not justify restoring an API-backed model path.
