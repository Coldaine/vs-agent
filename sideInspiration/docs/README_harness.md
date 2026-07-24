# Cloud harness package (`vs_harness/`)

Rescued from the orphaned Cursor cloud agent
[Vampire survivor AI harness](https://cursor.com/agents/bc-019f8ec1-f963-71e7-88f1-321413d4c567)
(branch `cursor/vs-agent-harness-c567`) and parked under `sideInspiration/`
for review. See the parent [`README.md`](../README.md) — adopt into `spine/`
only where needed; this is not a second authority stack.

Paths below are relative to `sideInspiration/` (run commands from that folder).

---
# Vampire Survivors Leader–Follower Agent Harness

Live (or simulated) agent harness for Vampire Survivors:

- **Perception**: SAM 3.1 concept masks → **threat union** (no track IDs), with a mock/sim backend for development
- **Pluggable movers**: `free_space_corridor`, `sector_density`, `potential_field`, `fast_vlm`
- **Commit / breakout wrapper**: momentum + power-through when escape is impossible
- **Strategy leader**: OpenAI-compatible endpoint for level-up / intent packets
- **Traces + bakeoff**: compare approaches empirically

## Host assumptions (RTX 5090 machine)

1. Vampire Survivors via Steam, **windowed / borderless** (not exclusive fullscreen)
2. Local GPU for SAM 3.1 (`perception.backend: sam3`) when available
3. OpenAI-compatible API for the leader (and optional `fast_vlm`):

```bash
export VS_OPENAI_BASE_URL="https://api.openai.com/v1"   # or your endpoint
export VS_OPENAI_API_KEY="..."
export VS_LEADER_MODEL="gpt-4o"
export VS_FOLLOWER_MODEL="gpt-4o-mini"
```

Check config:

```bash
python -m vs_harness.host_check --config configs/default.yaml
```

## Install

```bash
pip install -e ".[dev]"
# Optional live capture / keys:
# pip install mss pynput
# Optional SAM 3.1 (on the 5090 box):
# pip install torch
# pip install git+https://github.com/facebookresearch/sam3.git
```

## Quick start (simulator — no game required)

```bash
# Classic plan path: ~2 Hz VLM follower + slow leader
python3 -m vs_harness.cli run --config configs/vlm_follower.yaml --seconds 20

# Perception-mover path (free-space / sectors / potential field)
python3 -m vs_harness.cli run --config configs/default.yaml --approach free_space_corridor --seconds 20

# Bakeoffs + critique + host check
python3 -m vs_harness.bakeoff.runner --config configs/bakeoff.yaml
python3 -m vs_harness.cli critique runs/<run_id>.jsonl
python3 -m vs_harness.host_check --config configs/default.yaml
```

## Live game

1. Live mode is disabled in `sideInspiration/` — keep `loop.mode: sim` here.
   Adopt through `spine/` before any real-window control.
2. Classic plan config: `configs/vlm_follower.yaml` (`follower_hz: 2`, OpenAI-compatible follower + leader)
3. Or perception path: `perception.backend: sam3` / `yolo_world` with `host.capture_backend: mss`
4. Auto launch/attach via Steam app id `1794680` (or `host.launch_command`)
5. Kill switch: **F8**
6. `python3 -m vs_harness.cli run --config configs/vlm_follower.yaml`

Pixels + keys only in v1 (no memory reading).

## Architecture

```
Game/Sim → Capture → ModeDetect → PerceptionBackend (SAM / YOLO-World / flow / …)
        → ActiveMoverPlugin → CommitBreakoutWrapper → WASD
        → StrategyLeader (paused UI / slow intent)
        → TraceWriter (approach_id, masks, commit/breakout)
```

## Vision / VLM candidates (what to try next)

Full registry: [`configs/vision_candidates.yaml`](configs/vision_candidates.yaml). Print it with:

```bash
python3 -m vs_harness.cli vision-review
python3 -m vs_harness.bakeoff.perception_runner --config configs/perception_bakeoff.yaml
```

**Perception (movement geometry — prefer these over VLMs for dodge):**

| Backend | Idea | Why |
|---|---|---|
| `sam3` | SAM 3.1 concept masks → threat union | Best free-space carve; [facebookresearch/sam3](https://github.com/facebookresearch/sam3) (11.1k stars) |
| `yolo_world` | Open-vocab boxes → dilated mask | Much faster; coarser corridors; Ultralytics YOLO-World ([ultralytics/ultralytics](https://github.com/ultralytics/ultralytics) 59.8k stars) |
| `optical_flow` | Farneback magnitude prior | Fill between heavy ticks; weak alone |
| `fusion_*` | Detector OR flow | Cheap motion fill-in |
| `rfdetr` (future) | RF-DETR-Seg after fine-tune | Real-time masks once VS-labeled; [roboflow/rf-detr](https://github.com/roboflow/rf-detr) (8.7k stars) |

**Fast mover VLMs (bias / control — not sole dodge brain):** SmolVLM2 500M/256M locally via OpenAI-compatible server; MiniCPM-o; Moondream2. Remote `gpt-4o-mini` stays a slow control. Recent game-agent work shows tiny specialized controllers beat giant VLMs when latency dominates; slow→fast bridges help only if the slow model already beats fast-only.

**Slow leader:** Qwen2.5-VL / GPT-4o on paused level-ups (latency OK).

**Suggested 5090 bakeoff order:** `yolo_world` vs `sam3` vs `fusion_yolo_flow` (IoU + survive time), then movers with the winning perception; try local SmolVLM2 only as `fast_vlm` bias.

Context7 MCP was unavailable here — SAM / OpenAI-compatible APIs taken from public Meta/GitHub/Ultralytics docs.

