---
description: Explain the blocked G1 reflex-only path
agent: code
---

# G1 Reflex-Only Run

The active `spine\run.py` goal runtime does not implement `--reflex-only` or
`--disable-planner`. Do not run the obsolete command or claim G1 evidence.
G1 remains blocked until G0 is passed and a dedicated reflex-only entry path is
implemented and tested. Preserve the controller's neutralize-on-exit contract
when that path is added.

