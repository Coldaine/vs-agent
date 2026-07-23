# BLOCKED — runtime not provisioned for live gates

Halting the live loop per AGENTS.md ("environment broken → BLOCKED.md,
then stop"). The BUILDER code work is done:

## Code Updates (2026-07-23 Session 2)

### Fixed G0 Verifier (spine/verify_g0.py)
- Fixed `key_hold()` → `hold_direction()` and `menu_navigate()`
- Fixed Frame handling (accessing `.image` property)
- Added gate evidence output to status/gates.md
- Added one retry for key test
- Fixed movement test to verify camera displacement (camera-locked to player)
- Added evidence artifact saving (g0_capture.jpg)

### Fixed io_adapter.py
- Added missing `import time` (used by Frame.t_capture)
- Added missing `ocr()` method required by launch.py checkpoints
- Method signature: `ocr(region: tuple = None) -> str`

### Configured Tesseract OCR
- Added Tesseract path configuration in perceive.py
- Path: `C:\Program Files\Tesseract-OCR\tesseract.exe`
- Auto-configures on Windows when pytesseract is imported

### Updated .gitignore
- Added `.venv/` to prevent committing virtual environment
- Added `.env` to prevent committing credentials

### Previous Updates (2026-07-23 Session 1)
- **spine/run.py**: Added `--reflex-only` (strafe pattern) and `--disable-leader` modes.
- **spine/verify_perception.py**: Added G2 field-accuracy scoring (>90% requirement).
- **spine/model_client.py**: Added `AUDITOR` role for independent vision pass evaluation.
- All spine modules byte-compile; config.yaml parses.

## What was verified on this machine (2026-07-23)

- Python 3.13 + uv present.
- Steam installed; Vampire Survivors installed at
  `C:\Program Files (x86)\Steam\steamapps\common\Vampire Survivors`.
- ✓ .venv created with all dependencies installed
- ✓ All imports verified: openai, ultralytics, dxcam, pytesseract, yaml, cv2, numpy
- ✓ Tesseract OCR binary confirmed at standard Windows location
- **Available:** `DEEPSEEK_API_KEY` and `OPENROUTER_API_KEY` can be
  injected by any Doppler source selected by the launcher; no `.env` is
  required or used.
- **Missing:** detector weights from victorcoelh/vampire-survivors-bot;
  `yolo_weights` + `yolo_class_map` must be set in spine/config.yaml.
- **Missing:** Vampire Survivors game window (Steam is running but game not launched)

## What is needed to unblock

1. ✓ `pip install -r requirements.txt` — DONE (all packages in .venv)
2. ✓ Tesseract OCR binary on PATH — DONE (configured in perceive.py)
3. **BLOCKER:** Forked detector weights from victorcoelh/vampire-survivors-bot,
   with `yolo_weights` + `yolo_class_map` set in spine/config.yaml.
4. **BLOCKER:** Launch Vampire Survivors and set a FIXED windowed resolution,
   then calibrate `hud_regions` crop boxes in config.yaml to that resolution.

## Next Steps

Once blockers 3-4 are resolved:
1. Launch game: `doppler run -- python spine/launch.py` (or manual launch)
2. Enumerate game window: title, bounds, resolution
3. Set and record one fixed windowed resolution
4. Capture WGC frame and verify non-black
5. Test key registration with menu highlight diff
6. Test OCR-validated menu navigation to Antonio and Mad Forest
7. Test movement detection (camera displacement)
8. Run YOLO detector smoke test
9. Run G0 end-to-end: `doppler run -- python spine/verify_g0.py`
10. Begin G1 with reflex-only mode: `doppler run -- python spine/run.py --reflex-only`
