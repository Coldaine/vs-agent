"""input_health.py — probe whether the game is still accepting input.

A cheap truth check for the input layer: press a reversible probe key and
confirm the frame visibly changes. Used by the nav agent when two actions
in a row produce no change, and by io_adapter after a gamepad recreation
to confirm the new virtual pad landed in a live slot.
"""

from __future__ import annotations

import time

import numpy as np


def probe_health(io, threshold: float = 1.0) -> bool:
    """Press DOWN then UP and return True if the screen visibly changed.

    Returns False on any error so callers treat an unreadable probe as an
    unhealthy input path rather than crashing.
    """
    try:
        before = io.screenshot().image
        io.menu_navigate("down")
        time.sleep(0.3)
        io.menu_navigate("up")          # restore the original cursor position
        time.sleep(0.3)
        after = io.screenshot().image
        diff = float(np.mean(np.abs(before.astype(np.int16)
                                    - after.astype(np.int16))))
        return diff > threshold
    except Exception as error:
        print(f"[input_health] probe failed: {error}")
        return False
