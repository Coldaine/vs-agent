"""Keyboard-only, OCR-verified game launch and menu navigation."""

from __future__ import annotations

import re
import subprocess
import time

def launch_game(cfg: dict, io=None) -> bool:
    """Start Steam only when the game window is not already available."""
    if io is not None and io._game_window() is not None:
        return False
    subprocess.Popen([
        r"C:\Program Files (x86)\Steam\steam.exe",
        "-applaunch", str(cfg["steam_app_id"]),
    ])
    return True

def select_option(io, pick: str, options: list[str]) -> None:
    """planner-chosen level-up option. Options are vertically listed."""
    try:
        idx = [option.lower() for option in options].index(pick.lower())
    except ValueError:
        idx = 0
    for _ in range(idx):
        io.menu_navigate("down")
        time.sleep(0.2)
    io.menu_navigate("confirm")


