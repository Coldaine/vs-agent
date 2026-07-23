# BLOCKED — runtime not provisioned for live gates

Halting the live loop per AGENTS.md ("environment broken → BLOCKED.md,
then stop"). The BUILDER code work is done (all three seams filled,
one defect fixed, scaffolding added — see status/gates.md), but G0 and
everything downstream need a live environment that is not yet set up.

## What was verified on this machine (2026-07-23)

- Python 3.13 + uv present.
- Steam installed; Vampire Survivors installed at
  `C:\Program Files (x86)\Steam\steamapps\common\Vampire Survivors`.
- **Missing:** no `.env`; none of the runtime Python deps installed
  (openai, ultralytics/torch, dxcam, pydirectinput, pygetwindow,
  opencv-python, numpy, pytesseract); no `computer-control-mcp`; no
  detector weights; Tesseract OCR binary not confirmed.

## What is needed to unblock (details in status/HUMAN_NEEDED.md)

1. `.env` — FOLLOWER/LEADER (and optional REVIEWER) OpenAI-compatible
   URLs + keys + model names. Secrets: the human must create this; the
   BUILDER must not fabricate credentials.
2. `pip install -r requirements.txt` (or `uv pip install ...`).
3. Tesseract OCR binary on PATH (for pytesseract HUD/menu reads).
4. Forked detector weights from victorcoelh/vampire-survivors-bot,
   with `yolo_weights` + `yolo_class_map` set in spine/config.yaml.
5. Windowed mode at a FIXED resolution set once (never changed); then
   the `hud_regions` crop boxes in config.yaml calibrated to it.

Once 1–4 are in place, resume with G0:
`python spine/run.py` (or a G0 smoke sequence) verifies launch →
capture → keys → menu macro → move check, logging evidence to
status/gates.md.
