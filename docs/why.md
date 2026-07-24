# WHY.md — the reasoning behind the architecture

This document explains why the system is shaped the way it is. It is
written for the human and for any future agent that wonders why a
constraint exists. Every decision here traces to a specific failure
mode observed in game-playing agents or LLM self-improvement loops.

## 1. Why three agents instead of one smart one

Vampire Survivors has a bimodal decision cadence: thousands of
sub-second movement decisions per run, plus a few dozen slow,
high-leverage build decisions. No single model is good at both, and no
single latency budget serves both. So:

- pilot: fast, cheap, narrow (one of 9 movement tokens).
- planner: slower, smarter, rare (level-up picks, strategy briefs).
- BUILDER: never plays at all — maintains the system and the
  experiment loops.

The game itself drew this boundary: attacks are automatic, so movement
is the only real-time input, and level-ups pause the game, so strategy
is the only latency-free input. We separated along the seam the game
gave us.

## 2. Why a deterministic controller owns the keyboard

Because "the model said so" is not an arbitration policy. Three
proposers (reflex, pilot, planner) need rules for who wins, and
those rules must be:

- **Auditable** — every tick logs which rule fired, so post-mortems
  can distinguish "pilot was wrong" from "pilot was right but
  got vetoed."
- **Tunable** — thresholds live in config.yaml so the experiment loop
  can hill-climb them like any other variable.
- **Safe under latency** — the pilot is async; the controller acts
  on the freshest valid proposal plus reflex, never blocking on the
  VLM. This is what makes a 300-500ms model viable in a game that
  punishes 500ms of paralysis.

The reflex layer has veto power only, never goal-seeking. If reflex
could chase gems, the corpus would contain two entangled policies and
distillation would learn an incoherent mixture.

## 3. Why not just a VLM with the keyboard (the naive design)

Three measured problems:

1. **Latency variance, not mean latency, kills you.** API endpoints
   (and even local servers under load) have p95s 2-5x their mean.
   One slow call while surrounded = death. Hence the reflex floor.
2. **VLMs are weak on dense, cluttered scenes.** Late-game VS is
   hundreds of sprites plus particle effects. Small detectors (YOLO)
   localize threats better than any VLM at 100x lower cost. Hence
   perception is YOLO-first, VLM for judgment.
3. **Sub-4B models miss things on cluttered screens** (community
   probes show tiny models failing OCR and error-state detection).
   Hence the pilot floor is 4B zero-shot, with sub-4B viable only
   after distillation on our own corpus.

## 4. Why two optimization loops (P and C)

Loop C (game episodes) is the only ground truth, but it costs ~90
minutes per experiment. Most prompt hypotheses — output format,
priority ordering, wording — don't need the game; they need the
labeled eval set. Loop P replays 100 labeled frames offline in
minutes. The discipline: Loop P filters, Loop C confirms. A variant
must win Loop P to earn game time, and must win Loop C to ship.

The P-wins-C-loses case is the most informative outcome in the
project: it means the question is answerable but its answer doesn't
improve survival. Those results shape "what to even ask" — which is
a harder problem than "how to word the prompt."

## 5. Why keep/revert instead of "continuous improvement"

LLM self-critique loops without an external anchor degrade: agents
talk themselves into confident nonsense, and prompt changes accumulate
as noise. The anchor here is survived_s on fixed eval conditions
(Mad Forest, Antonio, no arcanas, fixed seed set). Every experiment:
one variable, 3 episodes, median +60s or full revert. Neutral results
revert too — a change that doesn't measurably help is technical debt
wearing a costume.

## 6. Why review happens in disposable sub-agents

Long-running agent contexts rot: they fill with stream-of-consciousness
until the model loses the plot (the Claude-Plays-Pokemon failure mode —
stuck in a loop for dozens of hours until a separate critic flagged
it). So: raw traces NEVER enter the builder's context. Fresh-context
sub-agents read curated packets, return strict JSON, and are
discarded. The builder consumes aggregates (failure histograms), not
traces. The schemas also force timestamp citations for every claim,
which makes reviewer hallucination checkable.

## 7. Why the death analysis looks 10-30s BEFORE the death

In VS, the killing blow is almost never the mistake — the mistake is
drifting toward a corner 20 seconds earlier. The autopsy prompt
therefore asks for "irreversible_at_s," not "cause of the final hit."
This is the difference between fixing symptoms and fixing policy.

## 8. Why the corpus is the real product

The endgame (gate G7) is a distilled micro-model — YOLO-class detector
plus a ~5M-param policy net at ~5ms — replacing the VLM pilot.
That requires (frame, state, action) triples with quality labels.
The VLM-pilot phase exists to manufacture that corpus: positive
examples from ticks where the agent survived the next 30s, corrective
examples from reviewer-flagged errors, plus human demonstration runs.
Without this plan, the project tops out at "a slow VLM plays okay
early game." With it, the VLM is a bootstrap teacher for something
100x faster.

## 9. Why eval conditions are frozen

Runs are high-variance (random level-up options, spawn patterns).
Comparing prompt versions across different stages or characters is
comparing noise. Fixed stage/character/seeds, 3-5 episodes, median not
mean. If a change to eval conditions is ever truly needed, all
champion scores are invalidated and re-baselined — never mixed.

## 10. Why computer-control-mcp instead of custom capture code

Screen capture of games fails in a specific way: GPU-accelerated
windows return black frames via traditional GDI screenshots. The MCP
server already solves this (WGC capture path) plus input injection,
OCR, and window management. Writing our own would be re-solving known
problems for zero differentiation. Our differentiation is the
controller, the loops, and the corpus — that's where the code goes.

## 11. Why there is an explicit reasoning stage (the THEORIST)

Diagnosis and mutation are not the same cognitive act. The autopsy
says WHAT happened; someone must still decide WHY, WHAT to change,
and HOW MUCH. Without a named stage for this, loops degrade into
"observe histogram -> tweak wording -> hope." So:

- **Video is never consumed as video.** The reasoning agent gets a
  keyframe strip (8-12 JPEGs, before/during/after triplets at the
  turning point) plus the numeric state window plus the current
  prompts/config. "Video understanding" is deliberately converted
  into "a dozen pictures and a spreadsheet," which VLMs do well.
- **Theories must cite frames and blame specific prompt text or
  config values** — a claim that can't point at evidence is astrology.
- **Scale is typed, not intuited.** The intervention ladder (1: one
  instruction; 2: priority reorder; 3: controller parameter at
  geometric ~30% steps; 4: structural, plateau-only) exists because
  "how big a change" is otherwise pure vibes. Rule: lowest sufficient
  level; never jump levels on weak evidence.
- **Every theory carries a falsifiable prediction with a
  falsified_if clause.** Verification then happens at two levels:
  MECHANISM (did the named failure class actually drop? — checked
  offline against the failure gallery first, then in vivo) and
  OUTCOME (survived_s +60s). Outcome-up-mechanism-flat is luck and
  gets probation (MECHANISM-UNCONFIRMED); mechanism-up-outcome-flat
  is a correct diagnosis with a wrong remedy
  (FALSIFIED-WITH-EVIDENCE) — the most valuable ledger entries.
- **theories.jsonl is the project's real memory.** Prompts are
  disposable; the record of which causal beliefs were tested and what
  happened is not. The theorist always receives prior theories in the
  same failure class so the loop reasons across weeks, including
  interaction effects ("theory #14 fixed cornering but raised
  attrition").
- **The theorist may decline.** {"causal_claim": null, "request": ...}
  turns "we don't know" into a data-collection task instead of a
  forced mutation. Forced mutations from insufficient evidence are
  how loops accumulate noise.

## 12. Why review calls carry inspection directives

Generic rubrics produce generic diagnoses. The controller already
logs every arbitration event (rule_fired), so review.py scans for
telemetry anomalies (override-rate spikes) and turns them into a
specific question the autopsy must answer FIRST ("was the pilot
wrong, or the reflex layer over-sensitive?"). This is the difference
between a post-mortem and a falsification tool. (Pattern borrowed
from 3D-scene agent workflows, where the orchestrator passes an
inspection directive with the render and bounding-box JSON; the
analogous blind-application of model corrections was deliberately
NOT borrowed — Blender mistakes cost a re-render, VS mistakes cost a
22-minute episode. Irreversibility is why the controller arbitrates.)

