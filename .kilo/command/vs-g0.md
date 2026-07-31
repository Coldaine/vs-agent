---
description: Run the complete G0 plumbing verifier
agent: code
---

# G0 Plumbing Gate

From the repository root, run `.venv\Scripts\python.exe spine\verify_g0.py`. This command is
allowed to launch the game, navigate verified menus, and perform the bounded movement check.
Report the JSON result and the appended `status/gates.md` evidence. Stop on any BLOCKED status.
