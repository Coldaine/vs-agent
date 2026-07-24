from __future__ import annotations

import time
from typing import Any

import numpy as np

from vs_harness.control.input_injector import InputInjector
from vs_harness.leader.strategy import StrategyLeader
from vs_harness.types import ScreenMode


# Placeholder option labels when OCR is unavailable — leader still ranks by knowledge.
DEFAULT_LEVELUP_OPTIONS = ["Weapon A", "Passive B", "Evolution C"]


def extract_levelup_options(frame_bgr: np.ndarray | None) -> list[str]:
    """Best-effort option text from a level-up panel.

    Sim/dev helper only: returns placeholders. Real OCR/VLM extraction belongs
    in an adopted spine path — never invent live card labels.
    """
    del frame_bgr  # unused until OCR is wired through spine
    return list(DEFAULT_LEVELUP_OPTIONS)


def handle_paused_ui(
    mode: ScreenMode,
    frame_bgr: np.ndarray | None,
    leader: StrategyLeader,
    injector: InputInjector,
    now_s: float,
) -> dict[str, Any]:
    """Choose a level-up/chest option and inject menu navigation keys."""
    if injector.live:
        raise RuntimeError(
            "Live menu handling is disabled in sideInspiration/vs_harness "
            "(no OCR/VLM option extraction; would always pick index 0). "
            "Use sim mode, or adopt menu selection through spine."
        )
    intent = leader.maybe_refresh(mode, frame_bgr, now_s)
    options = extract_levelup_options(frame_bgr)
    choice = leader.choose_levelup_option(options)
    # Navigate: assume leftmost selected; move right `choice` times, then confirm
    injector.release_all()
    time.sleep(0.05)
    for _ in range(choice):
        injector.tap("d")  # right
        time.sleep(0.05)
    _tap_confirm(injector)
    return {
        "mode": mode.value,
        "options": options,
        "choice_index": choice,
        "intent": intent.to_dict(),
    }


def _tap_confirm(injector: InputInjector) -> None:
    """Tap Enter / space for menu confirm when live backend allows."""
    if not injector.live or injector._backend is None:
        injector.tap("e")
        return
    kind, ctrl, KeyCode = injector._backend
    try:
        from pynput.keyboard import Key  # type: ignore

        ctrl.press(Key.enter)
        ctrl.release(Key.enter)
    except Exception:
        injector.tap("e")
