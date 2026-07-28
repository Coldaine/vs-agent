# HUMAN_NEEDED — fullscreen + unattended run

No model API key is needed. Auth is ChatGPT Pro OAuth via `codex login status`.

Before the next vision-menu / G0 attempt:

1. Open Vampire Survivors → **Options** → set **Fullscreen** (not windowed).
2. Leave it on the fixed capture monitor (the one used for WGC / `wgc_monitor_origin`).
3. Take one screenshot through the agent (or run prepare once) and set
   `capture_calibration_resolution` in `spine/config.yaml` to that exact
   fullscreen size. Remove any alternate oscillating windowed sizes.
4. Run unattended — do not use the desktop while the agent holds focus.
   Window flicker was what broke the last live entry (2560x1380 ↔ 2562x1479).

Suggested unattended command:

```powershell
.venv\Scripts\python.exe spine\run.py --entry-only --goal "Reach an in-game Mad Forest HUD as Antonio with all six modifiers false. Prefer keyboard. Stop once the run has started." --thread-id "g0-vision-fullscreen"
```

Adjudicate model-label disagreements in `eval_set/disagreements.json` only when G1.5 runs.
