from __future__ import annotations

from typing import Any

import numpy as np

from vs_harness.control.headings import vec_to_heading
from vs_harness.movers.base import Mover
from vs_harness.perception.masks import dilate_bool, distance_to_threat
from vs_harness.types import IntentPacket, MoverProposal, PerceptionFrame


class FreeSpaceCorridorMover(Mover):
    """Carve free space from threat union; steer toward fat corridors / goals."""

    approach_id = "free_space_corridor"

    def __init__(self, contact_dilate_px: int = 8, gem_weight: float = 0.35, orbit_bias: float = 0.15):
        self.contact_dilate_px = contact_dilate_px
        self.gem_weight = gem_weight
        self.orbit_bias = orbit_bias

    def propose(
        self,
        perception: PerceptionFrame,
        intent: IntentPacket,
        state: dict[str, Any] | None = None,
    ) -> MoverProposal:
        threat = dilate_bool(perception.threat_union, self.contact_dilate_px)
        dist = distance_to_threat(threat)
        px, py = perception.player_xy
        h, w = threat.shape
        ix, iy = int(np.clip(px, 0, w - 1)), int(np.clip(py, 0, h - 1))
        clearance = float(dist[iy, ix])

        # Sample goals on a ring; score by clearance along segment + attractors
        radii = [20, 40, 70]
        angles = np.linspace(0, 2 * np.pi, 24, endpoint=False)
        best_score = -1e9
        best_vec = (0.0, 0.0)
        gem_goal = self._gem_centroid(perception.gem_mask) if "gem" in intent.mode or "gem" in str(intent.attractors) or intent.mode == "gem_vacuum" else None
        if intent.mode == "farm" or "gems" in intent.attractors or "gem" in intent.attractors:
            gem_goal = self._gem_centroid(perception.gem_mask)

        for r in radii:
            for ang in angles:
                gx = px + r * np.cos(ang)
                gy = py + r * np.sin(ang)
                if gx < 2 or gy < 2 or gx >= w - 2 or gy >= h - 2:
                    continue
                score = self._path_clearance(dist, px, py, gx, gy)
                # Prefer higher clearance at goal
                gix, giy = int(gx), int(gy)
                score += 0.5 * float(dist[giy, gix])
                # Orbit bias
                tang = ang + (np.pi / 2 if intent.orbit == "cw" else -np.pi / 2 if intent.orbit == "ccw" else 0.0)
                score += self.orbit_bias * np.cos(tang - ang) * 0.0  # keep mild
                if intent.orbit == "cw":
                    score += self.orbit_bias * np.sin(ang)
                elif intent.orbit == "ccw":
                    score += self.orbit_bias * (-np.sin(ang))
                if gem_goal is not None and intent.mode in ("farm", "gem_vacuum"):
                    gdx, gdy = gem_goal[0] - px, gem_goal[1] - py
                    gnorm = (gdx**2 + gdy**2) ** 0.5 + 1e-6
                    align = ((gx - px) * gdx + (gy - py) * gdy) / (r * gnorm)
                    score += self.gem_weight * align * 20.0
                # Edge penalty
                edge = min(gx, gy, w - gx, h - gy)
                score += 0.05 * edge
                if score > best_score:
                    best_score = score
                    best_vec = (gx - px, gy - py)

        trapped = clearance < 6.0
        heading = vec_to_heading(best_vec[0], best_vec[1])
        urgency = float(np.clip(1.0 - clearance / 40.0, 0.0, 1.0))
        return MoverProposal(
            heading=heading,
            urgency=urgency,
            trapped=trapped,
            clearance_px=clearance,
            debug={"best_score": best_score, "goal_vec": best_vec},
        )

    @staticmethod
    def _gem_centroid(gem_mask: np.ndarray) -> tuple[float, float] | None:
        ys, xs = np.where(gem_mask)
        if len(xs) == 0:
            return None
        return float(xs.mean()), float(ys.mean())

    @staticmethod
    def _path_clearance(dist: np.ndarray, x0: float, y0: float, x1: float, y1: float, n: int = 10) -> float:
        xs = np.linspace(x0, x1, n)
        ys = np.linspace(y0, y1, n)
        h, w = dist.shape
        vals = []
        for x, y in zip(xs, ys):
            ix, iy = int(np.clip(x, 0, w - 1)), int(np.clip(y, 0, h - 1))
            vals.append(float(dist[iy, ix]))
        return float(np.min(vals))
