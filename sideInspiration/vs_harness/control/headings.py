from __future__ import annotations

import math

from vs_harness.types import HEADING_VEC, HEADINGS_8


def vec_to_heading(dx: float, dy: float, hold_eps: float = 1e-6) -> str:
    if abs(dx) < hold_eps and abs(dy) < hold_eps:
        return "HOLD"
    angle = math.atan2(dy, dx)  # 0 = East, positive = clockwise in image coords? atan2(y,x)
    # Convert to compass with N = -y
    # Our headings: N at atan2(-1,0) = -pi/2
    deg = math.degrees(angle)
    # Map: E=0, SE=45, S=90, SW=135, W=±180, NW=-135, N=-90, NE=-45
    sectors = [
        (0, "E"),
        (45, "SE"),
        (90, "S"),
        (135, "SW"),
        (180, "W"),
        (-180, "W"),
        (-135, "NW"),
        (-90, "N"),
        (-45, "NE"),
    ]
    best = "E"
    best_diff = 1e9
    for ref, name in sectors:
        diff = abs(((deg - ref + 180) % 360) - 180)
        if diff < best_diff:
            best_diff = diff
            best = name
    return best


def heading_to_vec(heading: str) -> tuple[float, float]:
    return HEADING_VEC.get(heading, (0.0, 0.0))


def heading_to_keys(heading: str) -> set[str]:
    keys: set[str] = set()
    if heading in ("N", "NE", "NW"):
        keys.add("w")
    if heading in ("S", "SE", "SW"):
        keys.add("s")
    if heading in ("E", "NE", "SE"):
        keys.add("d")
    if heading in ("W", "NW", "SW"):
        keys.add("a")
    return keys


def angle_delta(a: str, b: str) -> float:
    """Smallest angular difference in degrees between two 8-way headings."""
    if a == "HOLD" or b == "HOLD":
        return 180.0 if a != b else 0.0
    order = ["E", "SE", "S", "SW", "W", "NW", "N", "NE"]
    ia, ib = order.index(a), order.index(b)
    steps = min((ia - ib) % 8, (ib - ia) % 8)
    return steps * 45.0


def valid_heading(heading: str) -> bool:
    return heading in HEADINGS_8
