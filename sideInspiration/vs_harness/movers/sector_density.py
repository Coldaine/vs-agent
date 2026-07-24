from __future__ import annotations

from typing import Any

import numpy as np

from vs_harness.control.headings import vec_to_heading
from vs_harness.movers.base import Mover
from vs_harness.perception.masks import dilate_bool, distance_to_threat
from vs_harness.types import IntentPacket, MoverProposal, PerceptionFrame


class SectorDensityMover(Mover):
    approach_id = "sector_density"

    def __init__(self, sector_count: int = 16, contact_dilate_px: int = 8, gem_weight: float = 0.35):
        self.sector_count = sector_count
        self.contact_dilate_px = contact_dilate_px
        self.gem_weight = gem_weight

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
        yy, xx = np.mgrid[0:h, 0:w]
        dx = xx - px
        dy = yy - py
        ang = np.arctan2(dy, dx)
        sectors = np.floor(((ang + np.pi) / (2 * np.pi)) * self.sector_count).astype(int)
        sectors = np.clip(sectors, 0, self.sector_count - 1)

        # Density = mean threat in annulus
        radius = np.sqrt(dx * dx + dy * dy)
        annulus = (radius > 8) & (radius < 90)
        costs = []
        for s in range(self.sector_count):
            sel = annulus & (sectors == s)
            if not np.any(sel):
                costs.append(0.0)
                continue
            dens = float(threat[sel].mean())
            clear = float(dist[sel].mean())
            costs.append(dens * 10.0 - 0.2 * clear)

        # Gem attraction rotates cost
        if intent.mode in ("farm", "gem_vacuum") and perception.gem_mask.any():
            ys, xs = np.where(perception.gem_mask)
            gdx, gdy = float(xs.mean()) - px, float(ys.mean()) - py
            gang = np.arctan2(gdy, gdx)
            prefer = int(np.floor(((gang + np.pi) / (2 * np.pi)) * self.sector_count)) % self.sector_count
            costs[prefer] -= self.gem_weight * 3.0

        best = int(np.argmin(costs))
        center_ang = -np.pi + (best + 0.5) * (2 * np.pi / self.sector_count)
        vec = (float(np.cos(center_ang)), float(np.sin(center_ang)))
        ix, iy = int(np.clip(px, 0, w - 1)), int(np.clip(py, 0, h - 1))
        clearance = float(dist[iy, ix])
        return MoverProposal(
            heading=vec_to_heading(vec[0], vec[1]),
            urgency=float(np.clip(1.0 - clearance / 40.0, 0, 1)),
            trapped=clearance < 6.0,
            clearance_px=clearance,
            debug={"costs": costs, "best_sector": best},
        )
