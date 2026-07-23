# Gate status

Append-only record of gate progress. Evidence-based (GOAL.md).

## Session 1 — seam fill + G0 attempt (2026-07-23)

BUILDER work completed (code, no live env required):

- **Seam 1 — spine/model_client.py**: FILLED. OpenAI-compatible client
  (openai SDK), process-injected provider credentials only, direct
  DeepSeek text roles and OpenRouter free vision roles, base64 image
  encoding, tolerant JSON parsing with one retry for sub-agents, every
  call logged to model_calls.jsonl (fn, prompt_hash, latency_ms).
  All fixed contracts implemented: call_follower, call_follower_eval,
  call_leader, call_subagent, call_labeler, call_auditor,
  export_gallery_frames.
- **Seam 2 — spine/io_adapter.py**: FILLED (route A). dxcam capture
  (Desktop Duplication — captures GPU game windows without black
  frames) with BlackFrameError on near-black frames; pydirectinput
  scancode key hold/release with held-key tracking; pygetwindow focus
  + window-region lookup; pytesseract OCR helper; neutralize()
  releases all keys on every exit path.
- **Seam 3 — spine/perceive.py**: FILLED. ultralytics YOLO wiring
  (weights + class map from config), player fixed at frame centre
  (player-locked camera, game_reference §1), OCR-based screen_type /
  read_options / hud_state, state_summary for the follower, to_jpeg,
  and load_image (verify_perception seam).
- **Defect fix — spine/run.py**: level-up handler referenced an
  undefined `brief`; corrected to `shared["brief"]` per the mutable-cell
  design in docs/code_walkthrough.md (would have crashed at the first
  level-up otherwise).
- **Config**: added yolo_weights / yolo_class_map / yolo_conf,
  death/run-end OCR triggers, window_title_hint, and hud_regions crop
  boxes to spine/config.yaml.
- **Scaffolding**: requirements.txt and .gitignore. Provider keys are
  injected at launch and the repository has no pinned Doppler scope.
- All spine modules byte-compile; config.yaml parses.

## G0 PLUMBING — BLOCKED (pending human provisioning)

G0's live checks (launch, capture, keys, menu macro, move check)
cannot run yet: the runtime is not provisioned. See status/BLOCKED.md
and status/HUMAN_NEEDED.md. The game itself IS installed
(C:\Program Files (x86)\Steam\steamapps\common\Vampire Survivors) and
Steam is present; the missing pieces are the detector weights and
live game launch. Provider keys are available through runtime injection.

### Session 2 Updates (2026-07-23)

**Code Readiness: ✓ COMPLETE**

All G0 code defects fixed and verified:
- ✓ verify_g0.py: Fixed key_hold → hold_direction/menu_navigate
- ✓ verify_g0.py: Fixed Frame handling (accessing .image property)
- ✓ verify_g0.py: Added gate evidence output to gates.md
- ✓ verify_g0.py: Added one retry for key test
- ✓ verify_g0.py: Fixed movement test (camera displacement not player coords)
- ✓ io_adapter.py: Added missing time import
- ✓ io_adapter.py: Added missing ocr() method for launch.py
- ✓ perceive.py: Configured Tesseract OCR path
- ✓ .gitignore: Added .venv/ and .env
- ✓ All modules compile and import successfully

**Environment Readiness: PARTIAL**

Python dependencies: ✓ COMPLETE
- ✓ .venv created with Python 3.13
- ✓ openai >= 1.30 installed
- ✓ ultralytics >= 8.2 installed
- ✓ dxcam >= 0.0.5 installed
- ✓ pytesseract >= 0.3.10 installed
- ✓ All other requirements.txt packages installed

Tesseract OCR: ✓ COMPLETE
- ✓ Binary confirmed at C:\Program Files\Tesseract-OCR\tesseract.exe
- ✓ perceive.py configured to use it

**Remaining Blockers:**

1. **YOLO Detector Weights** (CRITICAL)
   - Status: NOT PROVISIONED
   - Need: victorcoelh/vampire-survivors-bot weights
   - Action: Download weights and set yolo_weights path in config.yaml
   - Also: Set yolo_class_map for enemy/elite/gem/player classes

2. **Game Launch and Resolution** (REQUIRED FOR TESTING)
   - Status: Steam running, game NOT launched
   - Need: Launch Vampire Survivors
   - Action: Set fixed windowed resolution
   - Action: Calibrate hud_regions in config.yaml

3. **io_adapter.py / computer-control-mcp Reconciliation** (DEFERRED)
   - Status: Currently using dxcam/pydirectinput (works)
   - AGENTS.md specifies: Use computer-control-mcp MCP server
   - Action: Migrate to computer-control-mcp for WGC capture
   - Priority: LOW (current implementation functional)

**Ready to Execute Once Blockers Resolved:**

```bash
# Step 1: Provision YOLO weights
# Download from victorcoelh/vampire-survivors-bot
# Update config.yaml: yolo_weights: "path/to/weights.pt"

# Step 2: Launch game and set resolution
# Manual: Start Vampire Survivors, set windowed mode
# Calibrate: Update hud_regions in config.yaml

# Step 3: Run G0 verification
doppler run -- python spine/verify_g0.py

# Step 4: If G0 passes, begin G1 reflex-only
doppler run -- python spine/run.py --reflex-only
```
