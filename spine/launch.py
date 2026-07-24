"""Keyboard-only, OCR-verified game launch and menu navigation."""

from __future__ import annotations

import re
import subprocess
import time


_CHARACTER_TOKENS = ("ANTONIO", "GENNARO", "IMELDA", "PASQUALINA", "ARCA")


def launch_game(cfg: dict, io=None) -> bool:
    """Start Steam only when the game window is not already available."""
    if io is not None and io._game_window() is not None:
        return False
    subprocess.Popen([
        r"C:\Program Files (x86)\Steam\steam.exe",
        "-applaunch", str(cfg["steam_app_id"]),
    ])
    return True


def _text(io) -> str:
    return " ".join(io.ocr().upper().split())


def classify_screen(io) -> tuple[str, str]:
    """Classify only menu/game states needed for deterministic G0 navigation."""
    text = _text(io)
    if "VAMPIRE SURVIVORS" in text:
        return "TITLE", text
    if "MAD FOREST" in text:
        return "STAGE_SELECT", text
    if any(token in text for token in _CHARACTER_TOKENS):
        return "CHARACTER_SELECT", text
    if re.search(r"\b\d{1,2}:\d{2}\b", text):
        return "IN_GAME", text
    if "START" in text or "ADVENTURE" in text:
        return "MAIN_MENU", text
    return "UNKNOWN", text


def _wait_for_state(io, expected: set[str], timeout_s: float = 12.0):
    deadline = time.monotonic() + timeout_s
    last_state, last_text = "UNKNOWN", ""
    while time.monotonic() < deadline:
        last_state, last_text = classify_screen(io)
        if last_state in expected:
            return last_state, last_text
        time.sleep(0.4)
    raise RuntimeError(
        f"expected one of {sorted(expected)}, got {last_state}: {last_text[:180]!r}")


def _block(io, message: str) -> None:
    import cv2

    frame = io.screenshot()
    cv2.imwrite("status/stuck.png", frame.image)
    with open("status/BLOCKED.md", "w", encoding="utf-8") as status:
        status.write(
            "# BLOCKED — deterministic menu navigation failed\n\n"
            f"{message}\n\n"
            "Evidence frame: `status/stuck.png`. Do not send further menu input "
            "until this state is reviewed.\n"
        )


def _press_and_expect(io, key: str, expected: set[str], timeout_s: float = 12.0):
    """Focus, send exactly one key, then prove the expected next state."""
    io.menu_navigate(key)
    return _wait_for_state(io, expected, timeout_s)


def ensure_main_menu(io, cfg: dict) -> tuple[str, str]:
    """Bring any known pre-run screen back to MAIN_MENU without blind inputs."""
    launch_game(cfg, io)
    try:
        state, text = _wait_for_state(
            io, {"TITLE", "MAIN_MENU", "CHARACTER_SELECT", "STAGE_SELECT"}, 20.0)
        for _ in range(3):
            if state == "MAIN_MENU":
                return state, text
            if state == "TITLE":
                state, text = _press_and_expect(io, "confirm", {"MAIN_MENU"})
            else:
                state, text = _press_and_expect(
                    io, "esc", {"TITLE", "MAIN_MENU", "CHARACTER_SELECT"})
        if state == "TITLE":
            return _press_and_expect(io, "confirm", {"MAIN_MENU"})
        raise RuntimeError(f"could not reach MAIN_MENU from {state}")
    except Exception as error:
        _block(io, f"Unable to reach MAIN_MENU: {error}")
        raise


def _select_antonio(io) -> None:
    """Character selection is horizontal; sweep left with OCR verification."""
    for _ in range(32):
        state, text = classify_screen(io)
        if state != "CHARACTER_SELECT":
            raise RuntimeError(f"left character select unexpectedly: {state}")
        if "ANTONIO" in text:
            return
        io.menu_navigate("left")
        time.sleep(0.25)
    raise RuntimeError("Antonio was not found after bounded left sweep")


def _select_mad_forest(io) -> None:
    """Stage selection is horizontal; Mad Forest is verified before confirming."""
    for _ in range(16):
        state, text = classify_screen(io)
        if state != "STAGE_SELECT":
            raise RuntimeError(f"left stage select unexpectedly: {state}")
        if "MAD FOREST" in text:
            return
        io.menu_navigate("left")
        time.sleep(0.25)
    raise RuntimeError("Mad Forest was not found after bounded left sweep")


def to_stage_select(io, cfg: dict) -> None:
    """Navigate MAIN_MENU -> Antonio -> Mad Forest; stop before starting a run."""
    try:
        ensure_main_menu(io, cfg)
        _press_and_expect(io, "confirm", {"CHARACTER_SELECT"})
        _select_antonio(io)
        _press_and_expect(io, "confirm", {"STAGE_SELECT"})
        _select_mad_forest(io)
    except Exception as error:
        _block(io, f"Unable to reach Mad Forest: {error}")
        raise


def start_run(io, cfg: dict) -> None:
    """Start the already-selected Mad Forest run and prove an in-game HUD appears."""
    try:
        _select_mad_forest(io)
        _press_and_expect(io, "confirm", {"IN_GAME"}, timeout_s=15.0)
    except Exception as error:
        _block(io, f"Unable to start Mad Forest: {error}")
        raise


def select_option(io, pick: str, options: list[str]) -> None:
    """Leader-chosen level-up option. Options are vertically listed."""
    try:
        idx = [option.lower() for option in options].index(pick.lower())
    except ValueError:
        idx = 0
    for _ in range(idx):
        io.menu_navigate("down")
        time.sleep(0.2)
    io.menu_navigate("confirm")
