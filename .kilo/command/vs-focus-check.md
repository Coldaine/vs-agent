---
description: Verify safe foreground activation for game input
agent: code
---

From the repository root, instantiate `IOAdapter`, call its verified `_focus()` method, and print
JSON confirming that the foreground window handle equals the exact `Vampire Survivors` handle.
Do not send any keyboard or mouse input.
