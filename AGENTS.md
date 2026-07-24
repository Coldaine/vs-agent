# AGENTS.md — repo conventions for the BUILDER

## READ THIS FIRST: who you are and what exists

There are THREE agents in this project. Do not confuse them.

1. **YOU are the BUILDER.** A coding agent. You write and maintain the
   harness, run the experiment loops in GOAL.md, and review scores.
   **You never play the game. You never watch frames in real time. You
   never make movement or level-up decisions.** If you find yourself
   reasoning about what the agent should do in a specific game
   situation, you have drifted into a role that is not yours — that
   reasoning belongs in prompts/ or config, executed by the other two
   agents.

2. **The pilot is an agent you are building.** A fast vision model
   behind OpenRouter's free vision router. At runtime
   it sees game frames and proposes movement directions. It is
   prompted by prompts/pilot.md. It does not exist as code you
   write — it is a model you configure. You improve it by mutating its
   prompt and by feeding the corpus, never by hardcoding its decisions.

3. **The planner is an agent you are building.** A DeepSeek V4 Flash
   text/reasoning model. At runtime it makes level-up choices and writes
   strategy briefs. Prompted by prompts/planner.md. Same rule: improve
   via prompt mutation, never by hardcoding picks.

The thing that actually drives the game is `spine/controller.py` — a
deterministic state machine (spec: docs/controller.md). The pilot
and planner only *propose*; the controller decides and is the sole
writer of keyboard input. Game I/O goes through `io_adapter.py`. 
Do not assume `computer-control-mcp` handles in-game logic since it lacks specific game integrations.

## Stack (see docs/stack.md and docs/why.md for rationale)

| Layer | Implementation | Status |
|---|---|---|
| Game I/O | `io_adapter.py` abstraction layer (supports keyboard, PWM, gamepad) | off the shelf |
| Reflex perception | forked from victorcoelh/vampire-survivors-bot (YOLOv8 enemy/gem detection) | fork, don't rebuild |
| Controller | `spine/controller.py` — deterministic arbiter FSM | you write this |
| pilot + labeler | OpenRouter `openrouter/free` vision router | configure, don't build |
| planner + reviewer | direct DeepSeek `deepseek-v4-flash` | configure, don't build |
| Glue | tick loop, level-up detector, trace logger, review runner, eval runner | ~300-500 lines target |

## Commands

- `python spine/run.py` — play one episode, write episodes/run_<n>/
- `python spine/run.py --seed-set eval` — one eval episode (fixed
  stage/character/seed list from spine/config.yaml)
- `python spine/replay_eval.py --prompt prompts/pilot.md` — Loop P:
  score a prompt variant against eval_set/ offline (no game needed)
- `python spine/review.py episodes/run_<n>` — spawn review sub-agents,
  append to failures.jsonl
- `python spine/verify_perception.py` — G2 gate: dump 20 frames +
  parsed states for human checking

## Conventions

- Model credentials are injected into the process, normally with
  `doppler run`; do not commit a `.env` file or Doppler scope. Required
  variables are `OPENROUTER_API_KEY` (pilot + labeler vision calls)
  and `DEEPSEEK_API_KEY` (planner + reviewer text calls). Endpoint URLs
  and default model IDs are fixed in `spine/model_client.py`.
- Two ways to involve the human, both via status/:
  status/HUMAN_NEEDED.md = normal checkpoint (gate sign-off, eval-set
  labeling, play session); pause that work and continue anything not
  blocked on it. status/BLOCKED.md = environment broken; halt fully.
- Every model call is logged: prompt hash, response, latency_ms.
  pilot latency p95 must stay <800ms; if it exceeds that for a
  full episode, the run is invalid for eval (outcome.json
  "invalid": true).
- Movement actions: N, NE, E, SE, S, SW, W, NW, HOLD. The pilot
  never issues menu clicks; the planner never issues movement. The
  controller enforces this — a proposal outside a layer's authority
  is discarded and logged as a protocol violation.
- Level-up detection: OCR on the pause overlay OR template match on
  the option card region — whichever is more reliable; measure both
  during G1 and keep the winner.
- Sub-agents (reviewers, theorist, Loop P generators) get fresh
  context, a packet, and a prompt from prompts/. They return JSON only.
  Their output goes to failures.jsonl, theories.jsonl, or
  loop_p_results.jsonl, never into your own context as raw traces.
- theories.jsonl is append-only and is the project's causal memory:
  every theory carries status CONFIRMED | FALSIFIED | UNRESOLVED |
  FALSIFIED-WITH-EVIDENCE. The theorist's packet must include prior
  theories in the same failure class.
- eval_set/gallery/ holds frames from autopsied failures with
  correct-action labels; it grows with every autopsy and is part of
  every Loop P replay.
- episodes/ and eval_set/ are append-only and immutable.
  experiments.log is append-only. Git commits after every experiment
  and every gate.

## When blocked

Write status/BLOCKED.md with: what you tried, exact error output,
what you need from the human. Then stop. Do not improvise around
input/capture problems by switching libraries silently.

