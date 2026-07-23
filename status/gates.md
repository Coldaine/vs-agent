# Gate status

Append-only record of gate progress. Evidence-based (GOAL.md).

## Session 1 — seam fill + G0 attempt (2026-07-23)

BUILDER work completed (code, no live env required):

- **Seam 1 — spine/model_client.py**: FILLED. OpenAI-compatible client
  (openai SDK), lazy `.env` loader, per-role endpoint resolution
  (FOLLOWER/LEADER/REVIEWER with REVIEWER→LEADER fallback), base64
  image encoding, tolerant JSON parsing with one retry for sub-agents,
  every call logged to model_calls.jsonl (fn, prompt_hash, latency_ms).
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
- **Scaffolding**: requirements.txt, .gitignore, .env.example.
- All spine modules byte-compile; config.yaml parses.

## G0 PLUMBING — BLOCKED (pending human provisioning)

G0's live checks (launch, capture, keys, menu macro, move check)
cannot run yet: the runtime is not provisioned. See status/BLOCKED.md
and status/HUMAN_NEEDED.md. The game itself IS installed
(C:\Program Files (x86)\Steam\steamapps\common\Vampire Survivors) and
Steam is present; the missing pieces are `.env`, the Python
dependencies, the detector weights, and (for OCR) the Tesseract binary.
