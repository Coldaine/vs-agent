---
description: Launch Vampire Survivors and report window readiness
agent: code
---

# Launch Check

From the repository root, run `& "C:\Program Files (x86)\Steam\steam.exe" -applaunch 1794680`.
Wait up to 30 seconds for the `Vampire Survivors` window, then run the project venv
Python to print JSON containing `process`, exact `window_title`, positive `width` and `height`,
and `ready: true`. Do not send game input.
