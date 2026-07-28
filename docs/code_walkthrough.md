# Code walkthrough — why every line in spine/ exists

Companion to why.md (which defends the architecture; this defends the
implementation). Organized per file. If you change a line, you should
be able to say why its justification no longer holds — otherwise don't.

## reflex.py — the safety floor

- `OCTANT_VEC` with +y down: screen coordinates, not math coordinates.
  Getting this wrong inverts N/S silently — the classic perception bug.
- `octant_of` rotates atan2 by +90 deg: atan2's zero is East; our
  octant zero is North (game-oriented, matches game_reference §6).
- `Detection.weight`, elites x3: an elite 200px away is more dangerous
  than a bat at 100px (game_reference §5, elite_burst). Weight divides
  distance in nearest_threat, pulling elites "closer" in the ranking.
- `nearest_threat` divides raw distance by weight: a single ranking
  that handles both swarms and elites without two code paths.
- `escape_vector` sums the k NEAREST threats (not all): distant waves
  shouldn't steer the escape; k from config so Loop C can tune it.
- Perpendicular nudge fires only when >50% of threat mass sits in the
  octant opposite the escape: that's the "single dominant cluster"
  case where directly-away splits clearance between flanks
  (game_reference §3.3). Below 50%, the swarm is distributed and the
  raw inverted sum is already the right answer — nudging would add
  zigzag. Rotation picks the EMPTIER adjacent side, not a fixed side.
- `veto_check` uses a 60 deg forward cone (dot > 0.5): threats behind
  you must not veto forward motion — otherwise the agent freezes when
  chased, which is the exact death we're preventing.
- Elite veto radius doubles: elite contact is burst damage
  (elite_burst in the taxonomy), so elites get a wider berth.

## controller.py — the arbiter

- Proposals carry a timestamp and go stale (staleness_ms): a VLM's
  answer to a frame from 900ms ago describes a world that no longer
  exists. Acting on it is worse than acting on reflex alone.
- Stale fallback = escape-if-threatened else KEEP CURRENT HEADING:
  keeps the agent moving (doctrine §3.1) without inventing goals.
  Goal-seeking is the pilot's job even in degradation (why.md §2).
- Dither suppression applies only to REVERSALS (dot < 0) and only on
  clean rules: a veto-driven reversal is new information and must
  never be suppressed — suppressing it would countermand the veto.
- Veto precedes staleness in the tick: a fresh-but-deadly proposal is
  worse than a stale one; order encodes the priority.
- `submit_pilot_proposal` returns False on out-of-vocab output:
  protocol violations are data (they measure pilot prompt drift),
  so they're logged, not silently coerced.
- neutralize() exists separately from tick logic so run.py's finally
  block can call it without knowing controller state.

## io_adapter.py — game I/O

- Virtual gamepad creation is verified by XInput slot enumeration, not a fixed sleep: ViGEm registers asynchronously and Unity/Rewired may cache empty slots if a device appears after launch.
- The adapter keeps exactly one VX360Gamepad alive for the process and closes it in every termination path; vgamepad/ViGEm objects left alive across crashes can poison later connections.
- Gamepad updates are wrapped with bounded recreate-on-error; neutralize() never recreates and never raises, preserving the fail-safe contract.
- If the game is already running before the virtual controller exists, the reliable path is to keep the controller alive and relaunch or return to a state where the game re-enumerates; late XInput devices are not guaranteed to be accepted.
- Steam Input and extra virtual controller drivers (vJoy, DS4Windows) can claim XInput slot 0 or remap the ViGEm device; disable Steam Input for the game or hide conflicting devices when the virtual pad is not accepted.
- Default backend is `keyboard` (pydirectinput scancode injection): stable, no driver dependencies, no XInput timing issues. The ViGEm/vgamepad gamepad backend remains in io_adapter.py and should be switched to (`input_backend: gamepad`) when analog-stick precision is required for fine movement control — keyboard is binary (pressed/released) so 8-direction and cannot express partial deflection.

## run.py — the episode

- pilot on a daemon THREAD, controller on the main thread: the VLM
  is async by design (controller.md). Daemon so a hung endpoint can't
  block shutdown. The finally block owns neutralize — every exit path,
  including exceptions and KeyboardInterrupt.
- `shared = {"brief": ...}` mutable cell: thread closures capture
  values, not variables — a plain `brief` string would freeze the
  pilot's brief at episode start, severing the planner→pilot
  channel. (Audit bug #1.)
- Level-up check BEFORE movement: the game pauses on level-up, so
  movement keys during the menu are garbage input; and the planner's
  pick is the highest-value decision in the run.
- `select_option` navigates by INDEX (down-arrow xN + confirm), not
  pixel clicks: menu layout is stable, pixel coordinates are not.
- Invalid-on-p95>800ms: a slow pilot makes the episode useless as
  eval evidence but still useful as corpus — hence marked, not deleted.
- prompt_hashes in outcome.json: every score attributable to exact
  prompt versions — the audit trail for KEEP/REVERT.

## review.py — diagnosis

- Directive = override-rate spike > 2x run median in a 60s window:
  anomalies, not averages, point at where the interesting failure
  lives. Median (not mean) because override rates are spiky.
- "full autopsy" as the literal fallback string: keeps the packet
  schema stable — the autopsy prompt always has a directive to answer.
- States sampled via the t%5 window AND the full final 60s: context
  budgets are finite; the death window gets full resolution because
  that's where the evidence is (why.md §7).
- Gallery growth happens HERE, not in the theorist: corrective data
  extraction is mechanical; reasoning about it is not. Separation of
  the mechanical and the cognitive is what keeps sub-agents cheap.

## replay_eval.py — Loop P

- Scores BOTH the base eval set and the gallery: a variant that only
  fixes its target failure while regressing normal play is a net loss
  (the >2% regression rule). GOAL.md's promotion gate lives here.
- Reports p50 AND p95: mean latency hides spikes; p95 is what kills
  agents (why.md §3.1).
- regression_check compares per-frame, not aggregate: aggregate scores
  can hide a 10% behavior flip behind a 2% accuracy gain.

## label_eval.py + labeler.md + auditor.md — G1.5

- Two passes, labeler then auditor, on the SAME frame: a single VLM
  pass grades its own homework. The auditor checks rubric APPLICATION
  (did it follow the decision procedure in order), not vibes — and
  must cite the violated rubric step to disagree. That asymmetry
  (easy to agree, expensive to disagree) keeps false disputes near
  zero so the human queue stays a handful of frames.
- "When uncertain, agree" in auditor.md: disagreements cost human
  time; the rubric is deterministic enough that genuine violations
  are unambiguous.
- Skip option in labeler.md: ambiguous frames (transitions, particle
  soup) produce wrong labels that poison every downstream metric.
  A skipped frame costs nothing; a wrong label costs trust in the
  eval set.

## launch.py — deterministic entry

- OCR checkpoint after EVERY menu step + one retry + escalate: blind
  sleeps are how menu macros desync overnight; escalating with a
  screenshot (status/stuck.png) turns a stalled night into a 2-minute
  human fix in the morning.
- Phantom-pick guard in select_option (idx=0 fallback): the planner
  WILL eventually name an option that doesn't exist; crashing the run
  over it wastes an episode, taking the first option loses one pick.

## trace.py

- states.jsonl flushed per line: an overnight crash must lose zero
  trace data — the corpus is the product (why.md §8).
- cause_of_death written as null at runtime: filled by review, never
  by the runtime — the runtime doesn't know why it died, and letting
  it guess contaminates the ledger.

## Runtime seams

`io_adapter` and `perceive` fail loudly when capture, input, OCR, or weights are
unavailable. `oauth_codex` fails closed unless Codex reports a ChatGPT login and
rejects inherited model API keys. `game_tools` bounds model proposals through
the deterministic controller. Plausible-looking fallback data or an API-backed
provider fallback would silently invalidate traces, so neither is permitted.
