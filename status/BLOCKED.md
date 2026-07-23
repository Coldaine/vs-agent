# BLOCKED — runtime not provisioned for live gates

Halting the live loop per AGENTS.md ("environment broken → BLOCKED.md,
then stop"). The BUILDER code work is done (all three seams filled,
one defect fixed, scaffolding added — see status/gates.md), but G0 and
everything downstream need a live environment that is not yet set up.

## What was verified on this machine (2026-07-23)

- Python 3.13 + uv present.
- Steam installed; Vampire Survivors installed at
  `C:\Program Files (x86)\Steam\steamapps\common\Vampire Survivors`.
- **Available:** `DEEPSEEK_API_KEY` and `OPENROUTER_API_KEY` can be
  injected by any Doppler source selected by the launcher; no `.env` is
  required or used.
- **Missing:** none of the runtime Python deps installed
  (openai, ultralytics/torch, dxcam, pydirectinput, pygetwindow,
  opencv-python, numpy, pytesseract); no detector weights; Tesseract OCR
  binary not confirmed. `uvx computer-control-mcp@latest` is available.

## What is needed to unblock (details in status/HUMAN_NEEDED.md)

1. `pip install -r requirements.txt` (or `uv pip install ...`).
2. Tesseract OCR binary on PATH (for pytesseract HUD/menu reads).
3. Forked detector weights from victorcoelh/vampire-survivors-bot,
   with `yolo_weights` + `yolo_class_map` set in spine/config.yaml.
4. Windowed mode at a FIXED resolution set once (never changed); then
   the `hud_regions` crop boxes in config.yaml calibrated to it.

Once 1–4 are in place, resume with G0 through a secret-injecting
launcher, for example `doppler run -- python spine/run.py`. It verifies launch →
capture → keys → menu macro → move check, logging evidence to
status/gates.md.
