# Handoff

Read `AGENTS.md`, `GOAL.md`, `docs/architecture.md`, and the active plan named
by `AGENTS.md` before changing the runtime.

The active model-driven entry point is `spine/run.py`; LangGraph state lives in
a local ignored SQLite checkpoint file. `spine/agent_subgraphs.py` defines the
separately compiled leader/follower graphs, `spine/codex_sdk_client.py` invokes
them through the official Python SDK/app-server, and `spine/game_tools.py`
bounds access to the deterministic game stack.

Authentication is the SDK/app-server's existing **ChatGPT-managed login**. It
is critically **not** an OpenAI API key or compatible HTTP endpoint. Do not use
Doppler, `.env`, `OPENAI_API_KEY`, `OPENROUTER_API_KEY`, or `DEEPSEEK_API_KEY`
for this runtime. Never inspect OAuth token files; use only public SDK account
metadata.

Both role threads explicitly configure `gpt-5.6-luna`; catalog availability is
separate from turn metadata. G0 remains in progress: a vision-led entry attempt
does not prove the required live HUD, modifier, input, and recovery evidence.
The controller remains the only movement-input writer. See `status/gates.md`
and `docs/architecture.md` for the current evidence and live boundaries.

Active work is the bounded G0 vertical slice. Prompts are externalized under
`prompts/`; capture retry hardening is recorded in the implementation history.
