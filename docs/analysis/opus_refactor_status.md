# Prompt Refactor Status

## Role Distribution (Updated)
- **Leader (Menu)**: Specialized vision-led state machine for navigating pre-game menus. Operates under a strict `menu_steps_budget`.
- **Leader (Gameplay)**: Strategic intent engine. Decides build direction (weapons/passives) and tactical priorities (boss focus, gem collection).
- **Follower (Reflex)**: Pure movement engine. Translates leader intent into an
  octant direction proposal validated by the deterministic controller.

## Key Changes
1. **Prompt Decoupling**: Moved hardcoded prompts from `agent_subgraphs.py` to `prompts/` Markdown files. 
2. **Budget Change**: Raised `menu_steps_budget` from 40 to 80 in `config.yaml`.
3. **Schema Compatibility**: `MENU_LEADER_SCHEMA` avoids `allOf`, which the Codex SDK rejects.

## Current G0 Progress
- Status: **IN PROGRESS**
- The entry trace is not G0 proof. HUD detection, modifier verification, input
  evidence, attach/recovery, and a two-second movement check remain required.

## Mission Log
- [x] Refactor prompts into external files.
- [x] Raise the menu budget.
- [ ] Verify In-Game HUD detection.
- [ ] Confirm Follower movement execution.
- [ ] Pass G0 Plumbing Gate.
