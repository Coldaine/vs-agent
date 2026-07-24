# HUMAN_NEEDED — one-time provisioning to start the gates

The BUILDER has filled all three seams and the harness compiles, but
the live environment needs five things only you can supply. None of
these are guesses the BUILDER may safely make (secrets, a fixed
resolution choice, and a trained model file).

## 1. Launch with provider keys injected

No `.env` is needed. Start the process through any Doppler project/config
that injects `DEEPSEEK_API_KEY` and `OPENROUTER_API_KEY`, for example:

```
doppler run -- python spine/run.py
```

The repository does not name or pin the Doppler source. DeepSeek is called
directly for leader/reviewer text roles; OpenRouter `openrouter/free` is used
for follower/labeler vision roles.

## 2. Install Python dependencies

```
cd d:\_projects\VampireSurvivor\vs-agent
uv pip install -r requirements.txt      # or: python -m pip install -r requirements.txt
```

(ultralytics pulls in torch — large. A CUDA build is recommended on
the RTX 5090.)

## 3. Tesseract OCR binary

pytesseract needs the Tesseract engine on PATH (HUD, timer, level-up
option text). Install it, then confirm `tesseract --version` works.

## 4. Detector weights (the reflex layer's eyes)

Fork the YOLOv8 weights from victorcoelh/vampire-survivors-bot (or the
CV alternative). Put the weights file somewhere stable and set in
`spine/config.yaml`:

- `yolo_weights: <path to .pt weights>`
- `yolo_class_map:` — map each of the model's class NAMES to one of
  `enemy | elite | gem | player`. Elites are weighted x3 automatically.

## 5. Fix the resolution + calibrate HUD crops (once, then never change)

Set Vampire Survivors to WINDOWED mode at a fixed resolution. Then fill
the `hud_regions` crop boxes `[x0, y0, x1, y1]` in `spine/config.yaml`
(hp, level, timer, level_up_options) measured in window pixels. Leave
them `null` only for a first smoke test; accurate HUD/leader behaviour
needs them.

## When done

Confirm here in writing, then the BUILDER resumes at G0 through Doppler
and records evidence in status/gates.md.
Delete status/BLOCKED.md when the environment is up.
