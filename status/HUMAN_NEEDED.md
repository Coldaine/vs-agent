# HUMAN_NEEDED — fullscreen + unattended run (Refreshed 2026-07-31)

No model API key is needed. Auth is ChatGPT Pro OAuth via `codex login status`. All naming conventions have been unified to `leader` and `follower` (eliminating `planner` and `pilot` references).

Before the next vision-menu / G0 attempt:

1. Open Vampire Survivors → **Options** → set **Fullscreen** (not windowed) on the correct physical monitor.
2. Leave the game on the fixed capture monitor (the one used for WGC / `wgc_monitor_origin`).
3. Run the prepare sequence or verify and set `capture_calibration_resolution` in `spine/config.yaml` to that exact fullscreen size. 
4. Run unattended — do not use the desktop while the agent holds focus, to prevent aspect ratio or coordinate scaling glitches.

Suggested unattended command for G0 entry verification (using unified leader/follower terminology):

```powershell
.venv\Scripts\python.exe spine\run.py --entry-only --goal "Reach an in-game Mad Forest HUD as Antonio with all six modifiers false. Prefer keyboard. Stop once the run has started." --thread-id "g0-vision-fullscreen"
```

Adjudicate model-label disagreements in `eval_set/disagreements.json` only when G1.5 runs.

