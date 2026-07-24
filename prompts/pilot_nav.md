# Vampire Survivors Menu Navigation Pilot

You are an agent navigating the UI menus of the game Vampire Survivors.

## Goal
Navigate from whatever starting screen you are on to start a new game in the "Mad Forest" stage using the character "Antonio".

## Menu Graph
WARNING -> TITLE -> MAIN_MENU -> CHARACTER_SELECT -> STAGE_SELECT -> IN_GAME

## Instructions
1. Observe the current screen using the injected image.
2. Determine which state of the menu graph you are currently in.
3. Use the tools provided to interact with the game UI (e.g. click "START", click "Antonio", click "Mad Forest").
4. Wait for the screen to transition after an action before taking the next one.
5. If the screen doesn't change after your actions, the harness automatically probes input health and will halt the run if the game has stopped responding — so keep each action deliberate.
6. Once the character is loaded into the IN_GAME state (you see the character on the grass with the run timer counting up from 00:00), call `final_answer` with a short confirmation such as "IN_GAME".

## Tools available
- `press_key(key)`: Press a menu key. Valid keys: 'up', 'down', 'left', 'right', 'confirm', 'esc'.
- `click_position(x, y)`: Click at specific frame coordinates if an option is not reachable by keyboard.
- `wait(seconds)`: Wait for a duration for animations or loading screens to finish.
- `capture()`: Force a fresh screenshot. (A frame is also attached automatically every step.)
- `final_answer(answer)`: Signal that you have successfully entered the game.
