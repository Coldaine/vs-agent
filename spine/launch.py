"""launch.py — game launch + deterministic menu macro.
Spec: docs/stack.md 'Launching the game'. OCR checkpoint after every
step; one retry; then escalate via status/HUMAN_NEEDED.md.
"""

from __future__ import annotations
import subprocess, time, sys


def launch_game(cfg):
    subprocess.Popen(["cmd", "/c", "start",
                      f"steam://rungameid/{cfg['steam_app_id']}"])
    time.sleep(20)                      # generous first-launch wait


def _checkpoint(io, expected_text: str, timeout_s: float = 15) -> bool:
    t0 = time.monotonic()
    while time.monotonic() - t0 < timeout_s:
        if expected_text.lower() in io.ocr().lower():
            return True
        time.sleep(1.0)
    return False


def to_stage_select(io, cfg):
    launch_game(cfg)
    steps = [  # (expected screen text, key to advance)
        ("VAMPIRE SURVIVORS", "confirm"),     # title
        ("START", "confirm"),                 # main menu
        ("CHARACTER", "confirm"),             # Antonio is default/first
        ("STAGE", None),                      # arrive at stage select
    ]
    for expected, key in steps:
        if key:
            io.menu_navigate(key)
        if not _checkpoint(io, expected):
            time.sleep(3)                     # one soft retry
            if not _checkpoint(io, expected, timeout_s=8):
                frame = io.screenshot()       # evidence for the human
                with open("status/stuck.png", "wb") as f:
                    f.write(__import__("perceive").to_jpeg(frame))
                with open("status/HUMAN_NEEDED.md", "w") as f:
                    f.write(f"Menu macro stuck expecting '{expected}'. "
                            "Screenshot saved in status/stuck.png. "
                            "Advance the menu manually, then confirm.")
                raise RuntimeError(f"menu macro failed at '{expected}'")


def start_run(io, cfg):
    io.menu_navigate("confirm")              # Mad Forest is stage 1
    _checkpoint(io, "confirm", timeout_s=5)
    io.menu_navigate("confirm")
    time.sleep(3)                            # run intro


def select_option(io, pick: str, options: list[str]):
    """Leader-chosen level-up option. Options are vertically listed;
    navigate by index, not by clicking."""
    try:
        idx = [o.lower() for o in options].index(pick.lower())
    except ValueError:
        idx = 0                               # model named a phantom; take first
    for _ in range(idx):
        io.menu_navigate("down")
        time.sleep(0.2)
    io.menu_navigate("confirm")
