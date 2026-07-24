"""Keyboard-only, OCR-verified game launch and menu navigation."""

from __future__ import annotations

import re
import subprocess
import time


_CHARACTER_TOKENS = ("CHARACTER SELECTION", "ANTONIO", "GENNARO", "IMELDA", "PASQUALINA", "ARCA")


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
    default = io.ocr(ocr_config="")
    header = io.ocr(ocr_config=io.config.get("menu_ocr_config"))
    return " ".join(f"{default} {header}".upper().split())


def classify_screen(io) -> tuple[str, str]:
    """Classify only menu/game states needed for deterministic G0 navigation."""
    text = _text(io)
    if "PHOTOSENSITIVITY WARNING" in text:
        return "WARNING", text
    if "MAD FOREST" in text:
        return "STAGE_SELECT", text
    if any(token in text for token in _CHARACTER_TOKENS):
        return "CHARACTER_SELECT", text
    if re.search(r"VAMPIRE\W{0,6}SURVIVORS", text):
        return "TITLE", text
    if re.search(r"\b\d{1,2}:\d{2}\b", text):
        return "IN_GAME", text
    if "START" in text or "ADVENTURE" in text:
        return "MAIN_MENU", text
    return "UNKNOWN", text


def _wait_for_state(io, expected: set[str], timeout_s: float = 12.0):
    deadline = time.monotonic() + timeout_s
    last_state, last_text = "UNKNOWN", ""
    while time.monotonic() < deadline:
        try:
            last_state, last_text = classify_screen(io)
            if last_state in expected:
                return last_state, last_text
        except Exception as error:
            last_text = f"capture pending: {error}"
        time.sleep(0.4)
    raise RuntimeError(
        f"expected one of {sorted(expected)}, got {last_state}: {last_text[:180]!r}")


def _block(io, message: str) -> None:
    import cv2

    evidence = "No frame available."
    try:
        frame = io.screenshot()
        cv2.imwrite("status/stuck.png", frame.image)
        evidence = "Evidence frame: `status/stuck.png`."
    except Exception as error:
        evidence = f"No evidence frame available: {error}"
    with open("status/BLOCKED.md", "w", encoding="utf-8") as status:
        status.write(
            "# BLOCKED — deterministic menu navigation failed\n\n"
            f"{message}\n\n"
            f"{evidence} Do not send further menu input "
            "until this state is reviewed.\n"
        )


def _press_and_expect(io, key: str, expected: set[str], timeout_s: float = 12.0):
    """Focus, send exactly one key, then prove the expected next state."""
    last_error = None
    for _ in range(2):
        io.menu_navigate(key)
        try:
            return _wait_for_state(io, expected, timeout_s / 2)
        except RuntimeError as error:
            last_error = error
    raise last_error


def ensure_main_menu(io, cfg: dict) -> tuple[str, str]:
    """Bring any known pre-run screen back to MAIN_MENU without blind inputs."""
    launch_game(cfg, io)
    try:
        state, text = _wait_for_state(
            io, {"WARNING", "TITLE", "MAIN_MENU", "CHARACTER_SELECT", "STAGE_SELECT"}, 45.0)
        for _ in range(4):
            if state in {"MAIN_MENU", "CHARACTER_SELECT", "STAGE_SELECT"}:
                return state, text
            if state in {"WARNING", "TITLE"}:
                state, text = _press_and_expect(
                    io, "confirm", {"TITLE", "MAIN_MENU", "CHARACTER_SELECT", "STAGE_SELECT"})
            else:
                state, text = _press_and_expect(
                    io, "esc", {"TITLE", "MAIN_MENU", "CHARACTER_SELECT", "STAGE_SELECT"})
        if state == "TITLE":
            return _press_and_expect(io, "confirm", {"MAIN_MENU", "CHARACTER_SELECT", "STAGE_SELECT"})
        raise RuntimeError(f"could not reach MAIN_MENU from {state}")
    except Exception as error:
        _block(io, f"Unable to reach MAIN_MENU: {error}")
        raise


def _select_antonio(io, cfg: dict) -> None:
    """Follow the calibrated D-pad path from the saved character selection."""
    for key in cfg.get("antonio_selection_path", ["up", "right"]):
        io.menu_navigate(key)
        time.sleep(0.25)


def _find_text_center(io, text_fragment: str) -> tuple[int, int] | None:
    """OCR the game frame and return the pixel center of the first text fragment match."""
    import pytesseract
    frame = io.screenshot()
    data = pytesseract.image_to_data(frame.image, output_type=pytesseract.Output.DICT)
    for i, text in enumerate(data["text"]):
        if text and text_fragment.upper() in text.upper():
            x, y, w, h = data["left"][i], data["top"][i], data["width"][i], data["height"][i]
            return (x + w // 2, y + h // 2)
    return None


def _click_text(io, text_fragment: str) -> bool:
    """Find a text fragment on screen and click its center."""
    pos = _find_text_center(io, text_fragment)
    if pos is None:
        return False
    io.click_frame(*pos)
    time.sleep(0.35)
    return True


def _confirm_character(io, cfg: dict) -> None:
    """Advance from CHARACTER_SELECT to STAGE_SELECT by clicking START."""
    if _click_text(io, "START"):
        _wait_for_state(io, {"STAGE_SELECT"}, timeout_s=8.0)
        return
    _press_and_expect(io, "start", {"STAGE_SELECT"}, timeout_s=8.0)


def to_stage_select(io, cfg: dict) -> None:
    """Navigate from any known screen through to STAGE_SELECT."""
    try:
        state, _ = ensure_main_menu(io, cfg)
        
        if state == "MAIN_MENU":
            _press_and_expect(io, "confirm", {"CHARACTER_SELECT"})
            _select_antonio(io, cfg)
            _confirm_character(io, cfg)
        elif state == "CHARACTER_SELECT":
            _select_antonio(io, cfg)
            _confirm_character(io, cfg)
        # state == "STAGE_SELECT" — already past character select
    except Exception as error:
        _block(io, f"Unable to reach Mad Forest: {error}")
        raise


def start_run(io, cfg: dict) -> None:
    """Confirm the selected stage and prove an in-game HUD appears."""
    try:
        _press_and_expect(io, "confirm", {"IN_GAME"}, timeout_s=15.0)
    except Exception as error:
        _block(io, f"Unable to start Mad Forest: {error}")
        raise


def select_option(io, pick: str | int, options: list[str]) -> None:
    """Leader-chosen level-up option. Options are vertically listed."""
    if isinstance(pick, int):
        idx = max(0, min(pick - 1, max(len(options) - 1, 0)))
    else:
        try:
            idx = [option.lower() for option in options].index(pick.lower())
        except ValueError:
            idx = 0
    for _ in range(idx):
        io.menu_navigate("down")
        time.sleep(0.2)
    io.menu_navigate("confirm")
