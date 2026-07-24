"""nav.py — G0 menu navigation via a smolagents vision agent.

A ``ToolCallingAgent`` drives Vampire Survivors' menus from whatever
screen the game boots into (WARNING -> TITLE -> MAIN_MENU ->
CHARACTER_SELECT -> STAGE_SELECT -> IN_GAME). Every step a callback
attaches the current game frame as the agent's observation image, so the
model reasons over live pixels rather than a stale description.

The agent only *proposes* menu inputs; io_adapter remains the sole writer
of input. If two consecutive actions produce no visible change, the input
health probe decides whether the game is still accepting input — a failed
probe writes status/BLOCKED.md and halts (no improvisation, per AGENTS.md).
"""

from __future__ import annotations

import os
import re
import time

import numpy as np
from PIL import Image

from smolagents import OpenAIServerModel, ToolCallingAgent, tool

try:                                    # ActionStep import path varies by version
    from smolagents import ActionStep
except ImportError:                     # pragma: no cover - older smolagents
    from smolagents.memory import ActionStep

import input_health

# Tools are module-level functions, so the active adapter/config are shared
# through module state set at the start of navigate_to_game().
_io = None
_cfg: dict = {}
_prev_frame = None
_no_change_steps = 0


def _pil_from_frame(frame) -> Image.Image:
    import cv2
    rgb = cv2.cvtColor(frame.image, cv2.COLOR_BGR2RGB)
    return Image.fromarray(rgb)


@tool
def press_key(key: str) -> str:
    """Press a single menu key to move the cursor or confirm a selection.

    Args:
        key: One of 'up', 'down', 'left', 'right', 'confirm', 'esc'.
    """
    _io.menu_navigate(key)
    time.sleep(0.5)
    return f"Pressed '{key}'."


@tool
def click_position(x: int, y: int) -> str:
    """Click an absolute pixel coordinate inside the captured game frame.

    Args:
        x: Horizontal pixel coordinate in the game frame.
        y: Vertical pixel coordinate in the game frame.
    """
    _io.click_frame(int(x), int(y))
    time.sleep(0.5)
    return f"Clicked ({x}, {y})."


@tool
def wait(seconds: float) -> str:
    """Wait for the given number of seconds so an animation or load can finish.

    Args:
        seconds: How long to wait, in seconds.
    """
    time.sleep(max(0.0, float(seconds)))
    return f"Waited {seconds}s."


@tool
def capture() -> str:
    """Take a fresh screenshot.

    The current frame is attached automatically to every step, so this is
    only needed to force a re-observation after a slow transition.
    """
    return "The latest game frame is attached to this step."


def _write_blocked(diff: float) -> None:
    with open("status/BLOCKED.md", "w", encoding="utf-8") as f:
        f.write("# BLOCKED — nav input health\n\n")
        f.write(
            "The menu-navigation agent saw two consecutive frames with no "
            f"visible change (mean pixel diff {diff:.3f}) and the input-health "
            "probe failed: the game is not accepting synthetic input.\n\n"
            "Halted without improvisation (AGENTS.md). Fix the input path "
            "(focus, backend, Steam Input) and re-run G0.\n")


def _screenshot_callback(memory_step: ActionStep, agent=None) -> None:
    """Attach the live frame to each step and guard against a dead input path."""
    global _prev_frame, _no_change_steps

    # Keep the context lean: drop images from steps older than the last two.
    if agent is not None:
        current = getattr(memory_step, "step_number", None)
        if current is not None:
            for prev in agent.memory.steps:
                prev_n = getattr(prev, "step_number", None)
                if isinstance(prev, ActionStep) and prev_n is not None \
                        and prev_n <= current - 2:
                    prev.observations_images = None

    frame = _io.screenshot()
    img = frame.image
    if _prev_frame is not None:
        diff = float(np.mean(np.abs(img.astype(np.int16)
                                    - _prev_frame.astype(np.int16))))
        if diff < float(_cfg.get("nav_no_change_threshold", 1.0)):
            _no_change_steps += 1
        else:
            _no_change_steps = 0
        if _no_change_steps >= 2:
            if not input_health.probe_health(_io):
                _write_blocked(diff)
                raise RuntimeError(
                    "nav: input-health probe failed — game not accepting input")
            _no_change_steps = 0
    _prev_frame = img
    memory_step.observations_images = [_pil_from_frame(frame)]


def _build_model(cfg: dict) -> OpenAIServerModel:
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        raise RuntimeError(
            "OPENROUTER_API_KEY is not injected — launch via Doppler with the "
            "OpenRouter key available in the child process.")
    return OpenAIServerModel(
        model_id=os.environ.get("NAV_MODEL", cfg.get("nav_model", "openrouter/free")),
        api_base="https://openrouter.ai/api/v1",
        api_key=key,
    )


def _verify_in_game(io, cfg: dict) -> bool:
    """Best-effort OCR check that an in-game run timer is on screen."""
    try:
        region = (cfg.get("hud_regions") or {}).get("timer")
        text = io.ocr(tuple(region) if region else None)
    except Exception:
        return False
    return bool(re.search(r"\d{1,2}\s*[:.]\s*\d{2}", text))


def navigate_to_game(io, cfg: dict) -> bool:
    """Drive the menus until the run has started. Returns True if an in-game
    timer is detected by OCR after the agent finishes."""
    global _io, _cfg, _prev_frame, _no_change_steps
    _io, _cfg, _prev_frame, _no_change_steps = io, cfg, None, 0

    with open("prompts/pilot_nav.md", "r", encoding="utf-8") as f:
        task = f.read()

    agent = ToolCallingAgent(
        tools=[press_key, click_position, wait, capture],
        model=_build_model(cfg),
        max_steps=int(cfg.get("nav_max_turns", 12)),
        step_callbacks=[_screenshot_callback],
    )
    agent.run(task)

    in_game = _verify_in_game(io, cfg)
    print(f"[nav] navigation finished; in_game_by_ocr={in_game}")
    return in_game
