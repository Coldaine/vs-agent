"""Keyboard-only, OCR-verified game launch and menu navigation."""

from __future__ import annotations

import re
import subprocess
import time


_CHARACTER_TOKENS = (
    "CHARACTER SELECTION", "ANTONIO", "GENNARO", "IMELDA", "PASQUALINA", "ARCA",
    # The live save's grid OCRs these newer characters more reliably than its
    # Character Selection heading after a cursor move.
    "RAMBA", "AMBROJOE",
)


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
    if "LEVEL UP" in text or "LEVELUP" in text:
        return "LEVEL_UP", text
    if "MAD FOREST" in text:
        return "STAGE_SELECT", text
    if "STAGE SELECTION" in text:
        return "STAGE_SELECT", text
    if "FILTER: OFF" in text:
        # Transitional menu screens can OCR poorly here but still require
        # character-select-level transitions.
        return "CHARACTER_SELECT", text
    if any(token in text for token in _CHARACTER_TOKENS):
        return "CHARACTER_SELECT", text
    # Character detail panels often OCR as noise but keep Rockstar + stat deltas.
    if "ROCKSTAR" in text and (
        "EGGS" in text
        or "SKIN" in text
        or "CO-OP" in text
        or re.search(r"[+\u2212\-]\s*\d+%", text)
    ):
        return "CHARACTER_SELECT", text
    if (
        re.search(r"VAMPIRE\W{0,12}SURVIVORS", text)
        or ("VAMPIRE" in text and "SURVIVOR" in text)
        or "FIRST SURVIV" in text
        or "CREDITS" in text
    ):
        return "TITLE", text
    if re.search(r"\b\d{1,2}:\d{2}\b", text):
        return "IN_GAME", text
    if "START" in text or "ADVENTURE" in text:
        return "MAIN_MENU", text
    return "UNKNOWN", text


def attach_live(io, cfg: dict) -> dict:
    """Attach to an already-live IN_GAME or LEVEL_UP screen without menu replay.

    Neutralizes held input first, classifies the live state, and returns a
    structured attach record. Refuses menu/title screens so callers cannot
    accidentally treat a pre-run screen as an attached episode.
    """
    from capture_transform import modifier_baseline

    io.neutralize()
    state, text = classify_screen(io)
    if state not in {"IN_GAME", "LEVEL_UP"}:
        raise RuntimeError(
            "attach requires an already-live IN_GAME or LEVEL_UP screen; "
            f"got {state}: {text[:180]!r}"
        )
    return {
        "attached": True,
        "state": state,
        "modifiers": modifier_baseline(cfg),
        "ocr": text[:240],
    }


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
        if last_state == "UNKNOWN" and "CHARACTER_SELECT" in expected:
            # Character-grid moves often OCR as noise while the menu is still
            # the character selector. Treat Rockstar + menu chrome as sticky.
            sticky = last_text.upper()
            if (
                "FILTER: OFF" in sticky
                or ("ROCKSTAR" in sticky and re.search(r"[+\u2212\-]\s*\d+%", sticky))
                or any(token in sticky for token in _CHARACTER_TOKENS)
            ):
                return "CHARACTER_SELECT", last_text
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
    io.menu_navigate(key)
    return _wait_for_state(io, expected, timeout_s)


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
                    io, "confirm", {"WARNING", "TITLE", "MAIN_MENU", "CHARACTER_SELECT", "STAGE_SELECT"})
            else:
                state, text = _press_and_expect(
                    io, "esc", {"WARNING", "TITLE", "MAIN_MENU", "CHARACTER_SELECT", "STAGE_SELECT"})
        if state == "TITLE":
            return _press_and_expect(io, "confirm", {"MAIN_MENU", "CHARACTER_SELECT", "STAGE_SELECT"})
        raise RuntimeError(f"could not reach MAIN_MENU from {state}")
    except Exception as error:
        _block(io, f"Unable to reach MAIN_MENU: {error}")
        raise


def select_character(io, cfg: dict) -> str:
    """Select the fixed eval character with bounded OCR-verified navigation."""
    target = str(cfg["character"]).upper()
    state, text = classify_screen(io)
    if state != "CHARACTER_SELECT":
        raise RuntimeError(f"cannot select {cfg['character']!r} from {state}: {text[:180]!r}")
    if target in text.upper():
        return text

    # Current Vampire Survivors combines a scrollable character grid with the
    # stage list.  The selected-card name is reliably readable in its detail
    # panel even when whole-frame OCR misses it. These coordinates are only
    # used at the fixed G0 capture resolution and are checked before confirm.
    scroll_top = cfg.get("character_scroll_top_frame")
    target_card = cfg.get("character_target_frame")
    label_region = cfg.get("character_selected_label_region")
    if scroll_top and target_card and label_region:
        io.click_frame(*scroll_top)
        time.sleep(0.35)
        io.click_frame(*target_card)
        time.sleep(0.35)
        label = " ".join(io.ocr(region=label_region, ocr_config="--psm 6").upper().split())
        if target in label:
            return label

    max_steps = int(cfg.get("character_search_max_steps", 32))
    directions = cfg.get("character_search_directions", ["up", "left", "right", "down"])
    for direction in directions:
        for _ in range(max_steps):
            state, text = _press_and_expect(
                io, direction, {"CHARACTER_SELECT"}, timeout_s=3.0)
            if target in text.upper():
                return text

    raise RuntimeError(
        f"could not select fixed eval character {cfg['character']!r} after bounded "
        f"character-menu search; last OCR: {text[:180]!r}")


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
    try:
        _press_and_expect(io, "confirm", {"STAGE_SELECT"}, timeout_s=6.0)
    except Exception:
        _press_and_expect(io, "start", {"STAGE_SELECT"}, timeout_s=8.0)


def select_stage(io, cfg: dict) -> str:
    """Select the fixed eval stage using bounded, OCR-verified navigation.

    The selected stage persists between runs, so merely arriving at the stage
    menu is not enough evidence that the next confirm is safe.  Every search
    move waits for the stage screen again and examines its OCR before making
    another move; this is deliberately a finite recovery search, not a blind
    sequence of sleeps.
    """
    target = str(cfg["stage"]).upper()
    state, text = classify_screen(io)
    if state != "STAGE_SELECT":
        raise RuntimeError(f"cannot select {cfg['stage']!r} from {state}: {text[:180]!r}")
    if target in text.upper():
        return text

    max_steps = int(cfg.get("stage_search_max_steps", 32))
    directions = cfg.get("stage_search_directions", ["up", "down"])
    for direction in directions:
        for _ in range(max_steps):
            state, text = _press_and_expect(
                io, direction, {"STAGE_SELECT"}, timeout_s=3.0)
            if target in text.upper():
                return text

    raise RuntimeError(
        f"could not select fixed eval stage {cfg['stage']!r} after bounded "
        f"stage-menu search; last OCR: {text[:180]!r}")


def to_stage_select(io, cfg: dict) -> None:
    """Navigate from any known screen through to STAGE_SELECT."""
    try:
        state, _ = ensure_main_menu(io, cfg)
        
        if state == "MAIN_MENU":
            _press_and_expect(io, "confirm", {"CHARACTER_SELECT"})
            select_character(io, cfg)
            _confirm_character(io, cfg)
        elif state == "CHARACTER_SELECT":
            select_character(io, cfg)
            _confirm_character(io, cfg)
        # state == "STAGE_SELECT" — already past character select
        select_stage(io, cfg)
    except Exception as error:
        _block(io, f"Unable to reach Mad Forest: {error}")
        raise


def start_run(io, cfg: dict) -> None:
    """Confirm the selected stage and prove an in-game HUD appears."""
    try:
        from capture_transform import modifier_baseline

        # Record the explicit baseline before the run starts so scored
        # episodes never silently inherit an incomplete modifier contract.
        modifier_baseline(cfg)
        target_stage = str(cfg["stage"]).upper()
        state, text = classify_screen(io)
        if state != "STAGE_SELECT" or target_stage not in text:
            raise RuntimeError(
                f"refusing to start: expected selected stage {cfg['stage']!r}, "
                f"got {state}: {text[:180]!r}")
        _press_and_expect(io, "confirm", {"IN_GAME", "LEVEL_UP"}, timeout_s=15.0)
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
