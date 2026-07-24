from __future__ import annotations

from typing import Any

import cv2
import numpy as np

from vs_harness.control.headings import vec_to_heading
from vs_harness.movers.base import Mover
from vs_harness.perception.masks import dilate_bool, distance_to_threat
from vs_harness.types import IntentPacket, MoverProposal, PerceptionFrame


class PotentialFieldMover(Mover):
    approach_id = "potential_field"

    def __init__(self, contact_dilate_px: int = 8, gem_weight: float = 0.35):
        self.contact_dilate_px = contact_dilate_px
        self.gem_weight = gem_weight

    def propose(
        self,
        perception: PerceptionFrame,
        intent: IntentPacket,
        state: dict[str, Any] | None = None,
    ) -> MoverProposal:
        threat = dilate_bool(perception.threat_union, self.contact_dilate_px).astype(np.float32)
        # Blur threat → smooth repulsive potential
        pot = cv2.GaussianBlur(threat, (21, 21), 6)
        if intent.mode in ("farm", "gem_vacuum") and perception.gem_mask.any():
            gems = perception.gem_mask.astype(np.float32)
            gems = cv2.GaussianBlur(gems, (21, 21), 6)
            pot = pot - self.gem_weight * gems

        # Gradient of potential (move downhill)
        gy, gx = np.gradient(pot)
        px, py = perception.player_xy
        h, w = pot.shape
        ix, iy = int(np.clip(px, 0, w - 1)), int(np.clip(py, 0, h - 1))
        # Move opposite gradient
        dx, dy = -float(gx[iy, ix]), -float(gy[iy, ix])
        if abs(dx) + abs(dy) < 1e-8:
            # Random-ish fallback: toward max distance
            dist = distance_to_threat(threat > 0.5)
            # Look at neighborhood
            y0, y1 = max(0, iy - 15), min(h, iy + 16)
            x0, x1 = max(0, ix - 15), min(w, ix + 16)
            patch = dist[y0:y1, x0:x1]
            my, mx = np.unravel_index(int(np.argmax(patch)), patch.shape)
            dx, dy = float(x0 + mx - ix), float(y0 + my - iy)

        dist = distance_to_threat(threat > 0.5)
        clearance = float(dist[iy, ix])
        return MoverProposal(
            heading=vec_to_heading(dx, dy),
            urgency=float(np.clip(1.0 - clearance / 40.0, 0, 1)),
            trapped=clearance < 6.0,
            clearance_px=clearance,
            debug={"grad": (dx, dy)},
        )
