# Agentic Piloting Architecture

The piloting infrastructure inside the Vampire Survivors loop separates semantic decision-making (LLM) from high-frequency deterministic translation (Reflex).

## Architecture

1. **Pilot (LLM)**
   - Acts as the goal-seeker.
   - Evaluates the current state (from YOLO + OCR perception).
   - Outputs a semantic macro-direction (`N`, `SW`, `HOLD`) and an optional `Speed` parameter (0.0 to 1.0).
   - Speed translates to an effective duty cycle in keyboard inputs (PWM) or analog scale in gamepad inputs.

2. **Reflex (Deterministic)**
   - Operates entirely on code with no model calls.
   - Processes the pilot's semantic direction against imminent threats.
   - Applies *Veto* rights: if the proposed pilot vector points into an elite or dense enemy cluster within the collision radius, Reflex overrides it with an optimal escape vector.
   - Applies *Staleness*: if the LLM's response time exceeds the `staleness_ms` threshold, the fallback is to maintain current heading or default to evasion.
   
3. **IO Adapter (Physical Layer)**
   - Abstraction over the physical input drivers (`pydirectinput`, `vgamepad`).
   - Converts the finalized `(Direction, Speed)` decision into driver commands.
   - PWM thread toggles inputs to simulate analog speed via duty cycle for keyboard backends.

## Nav Agent

Menu navigation introduces a distinct `smolagents` `ToolCallingAgent` that uses standard text + image reasoning equipped with tools (`press_key`, `click`, etc). Nav Agent verifies transitions inside the graph: `WARNING → TITLE → MAIN_MENU → CHARACTER_SELECT → STAGE_SELECT → IN_GAME`.
