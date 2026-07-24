# Trace spec — episodes/run_<n>/

Every episode writes exactly this structure. Append-only, immutable.

```
episodes/run_<n>/
  frames/            2fps JPEG capture, zero-padded: 000001.jpg
  states.jsonl       one line per tick:
    {
      "t": 12.5,                 # seconds since run start
      "hp": 61, "level": 4, "timer": "02:05",
      "inventory": ["whip", "garlic"],
      "threats_by_octant": [3,1,0,0,2,5,1,0],   # N,NE,E,SE,S,SW,W,NW
      "gems_by_octant":      [0,2,4,1,0,0,0,1],
      "reflex_override": false,
      "rule_fired": "clean",       # clean | veto | stale | dither
      "follower_latency_ms": 412,
      "action": "SE"
    }
  leader.jsonl       one line per level-up:
    {"t": 95.0, "options": [...], "pick": "...", "why": "...",
     "brief_update": "..."}
  keyframes/         run start, each level-up, t-60s before death,
                     death frame
  outcome.json
    {"survived_s": 612, "level": 14, "kills": 3211,
     "cause_of_death": null,        # filled by review, not at runtime
     "invalid": false,              # true if follower p95 > 800ms etc.
     "prompt_hashes": {"follower": "...", "leader": "..."}}
```

## Review packet (assembled by spine/review.py, fed to sub-agents)

- states.jsonl sampled 1 per 5s + ALL entries in final 60s
- the 6 keyframes
- outcome.json
- current follower.md + leader.md
- failure-type histogram from failures.jsonl (for label reuse)
- an INSPECTION DIRECTIVE, generated from telemetry:
  - scan rule_fired rates in 60s windows; any window where
    (veto+stale+dither)/ticks exceeds 2x the run median = anomaly
  - anomaly -> directive naming the window and the question
    ("was the follower wrong, or the reflex layer over-sensitive?")
  - no anomaly -> directive is the literal string "full autopsy"

## Theory packet (assembled for prompts/theorist.md)

- one failure record from failures.jsonl
- the keyframe strip for the failure window: 8-12 JPEGs, with
  before/during/after triplets at the turning point
- the states.jsonl window around the event
- current follower.md, leader.md, spine/config.yaml
- theories.jsonl entries for prior theories in the same failure class

## theories.jsonl (append-only causal ledger)

One line per theory:
{"id": 14, "failure_class": "...", "causal_claim": "...",
 "intervention": {...}, "prediction": {...}, "confidence": "...",
 "status": "UNRESOLVED"}
Status changes are APPENDED as new lines, never edited in place:
{"id": 14, "status_update": "CONFIRMED", "evidence": "exp/22-24",
 "t": "2026-07-25"}

## eval_set/ and the failure gallery

- eval_set/: 100 human-labeled frames (G1.5). Immutable.
- eval_set/gallery/: grows with every autopsy — the failure window's
  frames plus their correct-action labels from follower_errors
  (including threat_vector_at_t). Loop P replays must include the
  gallery: a variant must flip its target gallery frames without
  regressing >2% of the rest.

## Corpus use

- (frame, state, action) triples where reflex_override == false and the
  run survived past the next 30s = positive distillation examples.
- follower_errors from review sub-agents = corrective examples
  (frame, state, correct_action).
- Keep them in separate files: corpus/positive.jsonl,
  corpus/corrective.jsonl. Never mix without labels.
