# Stack rationale — what exists vs. what the BUILDER writes

## Off the shelf (do not rebuild)

1. **computer-control-mcp** — desktop control MCP server: screenshot
   (with WGC capture path for GPU/game windows — use WGC, plain GDI
   screenshots return black frames for games), key press/hold/release,
   OCR, window enumeration. Install: `uvx computer-control-mcp@latest`.
   This is the entire game I/O layer.

## Launching the game

- Vampire Survivors Steam app id: **1794680**.
  Launch: `steam steam://rungameid/1794680` (Steam must be logged in;
  starts silently, no Steam UI interaction).
- Windowed mode, fixed resolution, set once at G0 and never changed —
  template matches and click coordinates are resolution-dependent.
- Run start is a deterministic menu macro in spine/launch.py: VS menus
  are fully keyboard-navigable (arrows + Enter). Fixed sequence with an
  OCR checkpoint after each step (expected screen text), retry once on
  failure, then escalate. No blind sleeps longer than 5s.
- First launch only: dismiss Steam dialogs/cloud-sync prompts. If a
  dialog template is unknown, screenshot it for the trace and add a
  handler; do not click randomly.
2. **victorcoelh/vampire-survivors-bot** — plays the Steam version of
   Vampire Survivors with YOLOv8 enemy/item detection. Fork its
   detection weights/approach for the reflex layer's threat-by-octant
   computation. (LonesomeSoul/Vampire_survivors_bot_CV is a CV-based
   alternative reference.)
3. **Model endpoints** — OpenRouter's `openrouter/free` router provides
   the follower and labeler with free image-capable models; direct
   DeepSeek V4 Flash provides text-only leader/reviewer reasoning. Keys
   are injected into the process, normally through Doppler; this repo
   does not pin a Doppler project or config.

## Model selection (as of July 2026 — re-verify before G2)

- BUILDER: whatever the ChatGPT-OAuth Codex subscription serves.
- LEADER + review/theorist sub-agents: direct `deepseek-v4-flash`, with
  DeepSeek thinking effort set to `max` by default.
- FOLLOWER + labeler: `openrouter/free`, which selects a currently-free
  model compatible with image input. Free availability is transient, so
  benchmark a paid replacement before relying on it for evals.
- FOLLOWER local (RTX 5090, 32GB — preferred end state before
  distillation): trial in this order via vLLM's OpenAI server:
  Qwen3-VL-4B, Qwen3-VL-8B, Gemma 4 12B, InternVL3.5-8B
  (InternVL needs --trust-remote-code; cap input ~896px or visual
  tokens explode). Do not trial below 4B — sub-2B models miss things
  badly on cluttered screens.
- DISTILLED END STATE (G7): YOLO-class detector + ~5M-param policy
  net trained on corpus/. Not a VLM.

### Model trial method (offline, before G2)

1. Use the G1.5 capture (~500 frames) as trial input.
2. Serve candidates one at a time:
   `vllm serve <model> --dtype bfloat16 --max-model-len 8192 --port 8000`
3. Batch-eval each on the same 100 labeled frames: field accuracy,
   direction-agreement, latency p50/p95 at concurrency 1.
4. Winner = best accuracy among p95 < 500ms. Runner-up becomes the
   second-opinion model the controller may consult on disagreement.
   Log results in docs/analysis/model_trial.md.

## What the BUILDER writes (~300 lines target)

- `spine/run.py` — episode loop: launch/focus game window, tick at
  ~2Hz (MCP screenshot -> reflex layer -> follower call -> MCP key),
  level-up screen detection (OCR/template) -> leader call -> menu
  click, death detection, episode writer per docs/trace_spec.md.
- `spine/reflex.py` — threat vectors from YOLO detections; overrides
  follower direction when nearest enemy is within collision radius.
- `spine/review.py` — assembles review packets, spawns fresh-context
  review sub-agents (autopsy + build audit), writes failures.jsonl.
- `spine/verify_perception.py` — G2 gate helper.

## The three models (do not confuse roles)

- BUILDER (this agent): writes/maintains code and prompts; runs the
  experiment loop in GOAL.md. Never plays.
- FOLLOWER: real-time movement, 8-direction + HOLD, ~500ms cadence.
- LEADER: level-up picks, strategy brief, run strategy. Never steers.

## Known failure modes this design defends against

- Black screenshots on games -> WGC capture path.
- VLM latency spikes -> reflex override + p95 invalidation rule.
- Main-context rot from long traces -> review only in sub-agents,
  JSON-only output.
- Self-deluded "improvement" -> KEEP/REVERT hill-climb against
  survived_s only; unanchored self-critique is forbidden.
- Eval variance -> fixed stage/character, 3-5 runs per experiment,
  median not mean.
