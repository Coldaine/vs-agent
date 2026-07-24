# HANDOFF.md — read this before anything else

You are the BUILDER. This repo is a partially-built system for
autonomous Vampire Survivors play and self-improvement. The design is
finished and the deterministic core is written. Your job is to fill
three seams, verify against the live environment, and run the gates.

## Reading order (mandatory, in this order)

1. This file.
2. AGENTS.md — your role and the three-agent distinction.
3. GOAL.md — your standing orders. START HERE section is your goal.
4. docs/why.md — why every constraint exists.
5. docs/code_walkthrough.md — why every non-obvious LINE exists.
   Read before editing anything in spine/.
6. docs/stack.md, docs/controller.md, docs/trace_spec.md,
   docs/game_reference.md.

## What is PURPOSELY empty — do not "fix" the shape, fill the seams

These files raise NotImplementedError ON PURPOSE (see
code_walkthrough.md, final section — loud failure at seams is the
design, not a bug):

1. **spine/io_adapter.py** — game I/O bodies. Implement ONE backend,
   tried in route order: (A) NitroGen GamepadEnv, (B)
   computer-control-mcp, (C) thin MCP facade over GamepadEnv. One
   bounded diagnostic cycle per failing route, then move on.
2. **spine/model_client.py** — model endpoint calls. Credentials arrive
   through the process environment: direct DeepSeek for text roles and
   OpenRouter's free vision router for frame roles. Do not tie the repo to
   a particular Doppler project/config. Contracts in docstrings are fixed.
3. **spine/perceive.py** — YOLO/OCR wiring. Fork detection from
   victorcoelh/vampire-survivors-bot; elites get weight=3.0.

Everything else in spine/ is COMPLETE and correct as of the handoff
audit. Do not refactor it. If you believe a completed file is wrong,
cite the code_walkthrough.md justification you're overriding in your
commit message.

## What does not exist YET (expected — created at runtime or by gates)

- episodes/, eval_set/, status/, corpus/, *.jsonl logs, experiments.log
  — created by running the system.
- eval_set/labels.json — YOU build this at gate G1.5 via
  spine/label_eval.py (VLM-labeled, human sees only disagreements).
- status/ directory — create it; your communication channel to the
  human is status/HUMAN_NEEDED.md (pause one thread) and
  status/BLOCKED.md (full halt, environment broken only).

## What the human has already done / provides

- Steam installed, logged in, Vampire Survivors (app id 1794680)
  installed.
- Vampire Survivors set to WINDOWED mode at a fixed resolution.
  Never change it.
- A launcher that injects `DEEPSEEK_API_KEY` and `OPENROUTER_API_KEY`
  into the process (for example, `doppler run -- python spine/run.py`).
- computer-control-mcp available as an MCP server (route B).

## Rules that will feel like friction and are not negotiable

- Do not ask for approval between steps. Gates pass on logged
  evidence, not on the human saying so (exceptions: the physical
  checks listed in GOAL.md, via status/HUMAN_NEEDED.md).
- Do not write your own capture/input code outside io_adapter.py.
- Do not let any model output touch input without the controller.
- Do not mutate loop_p_generator.md, labeler.md, auditor.md, or
  episodes/ / eval_set/ / logs retroactively.
- docs/game_reference.md is ground truth for game knowledge; when a
  model's intuition disagrees, the reference wins.
- First session target: gates G0-G3. Do not skip to the experiment
  loops; G6 starts only when G0-G5 have logged evidence.

## When you're stuck

- Routine failure: one bounded diagnostic cycle, then try the next
  route or continue non-blocked work.
- Environment broken >30 min: status/BLOCKED.md with exact errors,
  then halt. Never improvise around capture/input failures.
- Need the human (rare): status/HUMAN_NEEDED.md with exact
  instructions, then continue anything not blocked on it.

## Side inspiration (cloud rescue)

Orphaned cloud harness work lives under `sideInspiration/` for review only.
See `sideInspiration/README.md`. It does not replace `spine/` or change gate order;
adopt tooling from it only where needed.
