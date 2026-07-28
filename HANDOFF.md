# Handoff

Read `AGENTS.md`, `GOAL.md`, `docs/architecture.md`, and the active file under `docs/plans/` before changing the runtime.

The current migration replaces the bespoke model loop with LangGraph. The active model-driven entry point is `spine/run.py`; LangGraph state lives in a local ignored SQLite checkpoint file, `spine/oauth_codex.py` invokes both roles, and `spine/game_tools.py` bounds access to the deterministic game stack.

Authentication is **ChatGPT Pro OAuth through Codex CLI only**. It is critically **not** an OpenAI API key and not an OpenAI-compatible HTTP endpoint. Do not use Doppler, `.env`, `OPENAI_API_KEY`, `OPENROUTER_API_KEY`, or `DEEPSEEK_API_KEY` for this runtime. Do not inspect OAuth token files; verify only with `codex login status`.

Both leader and follower currently use `gpt-5.6-luna`. The controller remains the only movement-input writer. Unit tests are not live game proof; consult `docs/architecture.md` for the remaining live boundaries.
