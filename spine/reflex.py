"""reflex.py — deterministic safety floor. Pure code, no model calls.

Authority: VETO ONLY. It may reject the follower's proposed direction
and substitute an escape vector. It may not pursue goals (no gem
chasing) — goal-seeking stays with the follower so the corpus teaches
one coherent policy (docs/why.md §2).

All thresholds come from config.yaml so Loop C can hill-climb them.
"""

from __future__ import annotations
import math
from dataclasses import dataclass

# unit vectors, index = octant (screen coords: +y is down)
OCTANT_VEC = {
    "N":  (0, -1), "NE": (1, -1), "E":  (1, 0), "SE": (1, 1),
    "S":  (0, 1),  "SW": (-1, 1), "W":  (-1, 0), "NW": (-1, -1),
}
OCTANT_ORDER = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]


@dataclass
class Detection:
    x: float
    y: float
    kind: str            # "enemy" | "elite" | "gem" | "player"
    weight: float = 1.0  # elites count x3 (game_reference §6)


def octant_of(dx: float, dy: float) -> str:
    ang = math.atan2(dy, dx)                      # screen coords
    idx = int(((math.degrees(ang) + 90 + 360) % 360) // 45) % 8
    return OCTANT_ORDER[idx]


def threats_by_octant(dets: list[Detection], player: Detection) -> list[int]:
    counts = [0] * 8
    for d in dets:
        if d.kind in ("enemy", "elite"):
            counts[OCTANT_ORDER.index(octant_of(d.x - player.x, d.y - player.y))] += int(d.weight)
    return counts


def gems_by_octant(dets: list[Detection], player: Detection) -> list[int]:
    counts = [0] * 8
    for d in dets:
        if d.kind == "gem":
            counts[OCTANT_ORDER.index(octant_of(d.x - player.x, d.y - player.y))] += 1
    return counts


def nearest_threat(dets: list[Detection], player: Detection) -> tuple[float, str] | None:
    best = None
    for d in dets:
        if d.kind not in ("enemy", "elite"):
            continue
        dist = math.hypot(d.x - player.x, d.y - player.y) / d.weight
        if best is None or dist < best[0]:
            best = (dist, octant_of(d.x - player.x, d.y - player.y))
    return best


def escape_vector(dets: list[Detection], player: Detection, k: int) -> str:
    """Sum the k nearest threat vectors, invert, return octant.
    Perpendicular preference (game_reference §3.3): if the raw escape
    octant points directly away from a single dominant threat cluster,
    rotate 45 deg toward the emptier adjacent side — directly-away
    splits clearance between two flanks and traps you between waves."""
    threats = sorted(
        (d for d in dets if d.kind in ("enemy", "elite")),
        key=lambda d: math.hypot(d.x - player.x, d.y - player.y),
    )[:k]
    if not threats:
        return "HOLD"
    vx = sum((player.x - d.x)*d.weight for d in threats)
    vy = sum((player.y - d.y)*d.weight for d in threats)
    escape = octant_of(vx, vy)

    counts = [0] * 8
    for d in threats:
        counts[OCTANT_ORDER.index(octant_of(d.x - player.x, d.y - player.y))] += int(d.weight)
    esc_idx = OCTANT_ORDER.index(escape)
    threat_idx = (esc_idx + 4) % 8          # the octant we flee FROM
    total = sum(counts)
    if total and counts[threat_idx] / total > 0.5:
        left = counts[(esc_idx + 1) % 8]
        right = counts[(esc_idx - 1) % 8]
        esc_idx = (esc_idx + 1) % 8 if left <= right else (esc_idx - 1) % 8
        escape = OCTANT_ORDER[esc_idx]
    return escape


def veto_check(proposed: str, dets: list[Detection], player: Detection,
               collision_radius_px: float) -> bool:
    """True if the proposal must be vetoed: a threat lies within the
    collision radius along the proposed direction."""
    if proposed in ("HOLD", None):
        return False
    pv = OCTANT_VEC[proposed]
    plen = math.hypot(*pv)
    for d in dets:
        if d.kind not in ("enemy", "elite"):
            continue
        dx, dy = d.x - player.x, d.y - player.y
        dist = math.hypot(dx, dy)
        if dist > collision_radius_px * (2 if d.kind == "elite" else 1):
            continue
        # is the threat roughly along the proposed direction?
        dot = (dx * pv[0] + dy * pv[1]) / (dist * plen + 1e-9)
        if dot > 0.5:  # within ~60 deg cone ahead
            return True
    return False
