# HUMAN_NEEDED — remaining live-game calibration

No model API key is needed or permitted. Do not launch through Doppler and do not inject `OPENAI_API_KEY`, `OPENROUTER_API_KEY`, or `DEEPSEEK_API_KEY`. The LangGraph runtime uses the existing ChatGPT Pro OAuth session owned by Codex CLI; verify only with `codex login status`.

The remaining human-visible work is limited to live-game evidence:

1. Confirm the fixed window resolution and DPI have not changed since G0 calibration.
2. Verify the stage-selection UI matches all six explicit modifier values in `spine/config.yaml`: Hyper off, Hurry off, Arcanas off, Limit Break off, Inverse off, Endless off.
3. Adjudicate only model-label disagreements written to `eval_set/disagreements.json` when G1.5 runs.

Dependencies, Tesseract, and threat weights are already locally present. Gem/elite perception and attach/recovery remain implementation work, not requests for a model credential.
