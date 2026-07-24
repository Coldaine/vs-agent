# Controller spec — spine/controller.py

The controller is a deterministic finite-state arbiter. It is the ONLY
component that writes keyboard input. Models propose; the controller
disposes. There is no model judgment inside the controller — every
rule below is a threshold or a lookup, and every threshold lives in
spine/config.yaml so the experiment loops can tune it.

## Authority hierarchy

| Layer | Can do | Cannot do | When consulted |
|---|---|---|---|
| Reflex (pure code) | VETO the follower's direction; substitute escape vector | choose strategy, chase gems | every tick, before any key event |
| Follower (VLM) | PROPOSE one of 8 directions or HOLD | issue keys, see menus, override a reflex veto | every tick, async |
| Leader (LLM) | choose menu options; rewrite the strategy brief | steer movement, issue keys | only on LEVEL_UP screen |
| Controller | everything — sole input writer | exercise judgment (it is rules) | always |

A proposal outside a layer's authority (e.g. follower emitting a menu
click) is discarded and logged as a protocol violation.

## Tick loop (~2Hz)

```
1. PERCEPT  frame <- computer-control-mcp screenshot (WGC path)
            state  <- YOLO detections + OCR: threats/gems by octant,
                      player pos, HP, timer, screen_type
2. SCREEN   if screen_type == LEVEL_UP:
              freeze movement, send frame to leader,
              execute leader pick via menu click, resume. Done.
3. VETO     if nearest enemy < collision_radius along the follower's
            proposed direction:
              discard proposal; action <- reflex escape vector
4. STALE    if follower's freshest proposal is older than
            staleness_ms (default 800):
              action <- reflex layer alone; mark tick degraded
5. DITHER   if proposed direction reverses heading within dither_ms
            (default 300) and no veto fired: keep current heading
6. COMMIT   press/hold winning direction via computer-control-mcp
7. LOG      append tick to states.jsonl, including which rule fired
            (veto | stale | dither | clean) and follower_latency_ms
```

## Key design decisions (the why — see docs/why.md for depth)

- **The follower is async.** The controller never blocks on the VLM.
  It acts on the freshest valid proposal plus reflex. A 300-500ms
  model is compatible with a game that punishes 500ms of paralysis
  because the reflex layer keeps the agent alive between proposals;
  the VLM steers the drift, it does not react.
- **Veto, not override.** The reflex layer can only say "no, that way
  is death" — it cannot pursue goals. Goal-seeking stays with the
  follower so the corpus teaches one coherent policy.
- **Anti-dither exists because VLMs oscillate** between two equally
  good octants; heading reversals cost distance and look like
  indecision to the review sub-agents.
- **Every arbitration event is logged.** Override rate (veto+stale
  ticks / total ticks) is the objective health metric of the follower.
  Sustained override rate >30% = the follower is weak; prioritize
  corpus distillation over further prompt tuning.

## Tunable parameters (spine/config.yaml — Loop C may mutate these)

```
tick_hz: 2
collision_radius_px: 90
staleness_ms: 800
dither_ms: 300
escape_vector_k: 5        # nearest-k enemies in reflex vector sum
gem_pull_weight: 0.3      # reflex-layer bias toward gem octants
```
