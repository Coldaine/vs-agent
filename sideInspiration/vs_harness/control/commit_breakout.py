from __future__ import annotations

from typing import Any

import numpy as np

from vs_harness.control.headings import angle_delta, heading_to_keys, heading_to_vec, vec_to_heading
from vs_harness.perception.masks import dilate_bool, distance_to_threat
from vs_harness.types import ControlCommand, MoverProposal, PerceptionFrame, WrapperMode


class CommitBreakoutWrapper:
    """Shared commit / momentum / breakout layer over any mover proposal."""

    def __init__(
        self,
        enabled: bool = True,
        commit_ms: float = 220.0,
        breakout_commit_ms: float = 450.0,
        clearance_trap_px: float = 6.0,
        momentum_weight: float = 0.4,
        stuck_motion_px: float = 2.0,
        stuck_frames: int = 8,
        contact_dilate_px: int = 8,
        approach_id: str = "unknown",
    ):
        self.enabled = enabled
        self.commit_ms = commit_ms
        self.breakout_commit_ms = breakout_commit_ms
        self.clearance_trap_px = clearance_trap_px
        self.momentum_weight = momentum_weight
        self.stuck_motion_px = stuck_motion_px
        self.stuck_frames = stuck_frames
        self.contact_dilate_px = contact_dilate_px
        self.approach_id = approach_id

        self._committed_heading = "HOLD"
        self._commit_until = 0.0
        self._mode = WrapperMode.PASSTHROUGH
        self._last_xy: tuple[float, float] | None = None
        self._stuck = 0

    def apply(
        self,
        proposal: MoverProposal,
        perception: PerceptionFrame,
        now_s: float,
    ) -> ControlCommand:
        if not self.enabled:
            return ControlCommand(
                heading=proposal.heading,
                keys=heading_to_keys(proposal.heading),
                wrapper_mode=WrapperMode.PASSTHROUGH,
                approach_id=self.approach_id,
                urgency=proposal.urgency,
                debug={"wrapper": "off"},
            )

        # Stuck detector
        if self._last_xy is not None:
            dx = perception.player_xy[0] - self._last_xy[0]
            dy = perception.player_xy[1] - self._last_xy[1]
            if (dx * dx + dy * dy) ** 0.5 < self.stuck_motion_px and proposal.clearance_px < self.clearance_trap_px * 2:
                self._stuck += 1
            else:
                self._stuck = 0
        self._last_xy = perception.player_xy

        trapped = proposal.trapped or proposal.clearance_px < self.clearance_trap_px or self._stuck >= self.stuck_frames

        # Active commit holds
        if now_s < self._commit_until and self._committed_heading != "HOLD":
            heading = self._committed_heading
            mode = self._mode if self._mode != WrapperMode.PASSTHROUGH else WrapperMode.COMMITTED
            return ControlCommand(
                heading=heading,
                keys=heading_to_keys(heading),
                wrapper_mode=mode,
                approach_id=self.approach_id,
                urgency=proposal.urgency,
                debug={"held_commit": True, "clearance": proposal.clearance_px},
            )

        if trapped:
            heading = self._breakout_heading(perception)
            self._committed_heading = heading
            self._commit_until = now_s + self.breakout_commit_ms / 1000.0
            self._mode = WrapperMode.BREAKOUT
            self._stuck = 0
            return ControlCommand(
                heading=heading,
                keys=heading_to_keys(heading),
                wrapper_mode=WrapperMode.BREAKOUT,
                approach_id=self.approach_id,
                urgency=1.0,
                debug={"breakout": True, "clearance": proposal.clearance_px},
            )

        # Momentum: resist large reversals
        heading = proposal.heading
        if self._committed_heading not in ("HOLD",) and heading not in ("HOLD",):
            if angle_delta(heading, self._committed_heading) >= 135 and proposal.clearance_px > self.clearance_trap_px * 1.5:
                # allow only if much safer — else keep momentum
                if self.momentum_weight > 0.2:
                    heading = self._committed_heading

        self._committed_heading = heading
        self._commit_until = now_s + self.commit_ms / 1000.0
        self._mode = WrapperMode.COMMITTED
        return ControlCommand(
            heading=heading,
            keys=heading_to_keys(heading),
            wrapper_mode=WrapperMode.COMMITTED,
            approach_id=self.approach_id,
            urgency=proposal.urgency,
            debug={"clearance": proposal.clearance_px},
        )

    def _breakout_heading(self, perception: PerceptionFrame) -> str:
        """Pick thinnest threat wall toward freer space (ray cast)."""
        threat = dilate_bool(perception.threat_union, self.contact_dilate_px)
        dist = distance_to_threat(threat)
        px, py = perception.player_xy
        h, w = threat.shape
        best = None
        best_score = -1e9
        for ang in np.linspace(0, 2 * np.pi, 32, endpoint=False):
            thickness = 0.0
            beyond = 0.0
            hit_free = False
            for r in range(1, 90):
                x = int(px + r * np.cos(ang))
                y = int(py + r * np.sin(ang))
                if x < 0 or y < 0 or x >= w or y >= h:
                    break
                if threat[y, x] and not hit_free:
                    thickness += 1.0
                else:
                    if thickness > 0:
                        hit_free = True
                        beyond += float(dist[y, x])
                        if beyond > 30:
                            break
                    else:
                        # already in free along this ray
                        beyond += float(dist[y, x])
            edge_pen = 0.0
            ex = px + 80 * np.cos(ang)
            ey = py + 80 * np.sin(ang)
            edge_pen = max(0.0, 10.0 - min(ex, ey, w - ex, h - ey))
            # Prefer thin wall + high clearance beyond
            score = -thickness * 3.0 + beyond * 0.2 - edge_pen
            if score > best_score:
                best_score = score
                best = (np.cos(ang), np.sin(ang))
        if best is None:
            return "N"
        return vec_to_heading(float(best[0]), float(best[1]))


def build_wrapper(cfg: dict[str, Any], approach_id: str, enabled: bool | None = None) -> CommitBreakoutWrapper:
    w = cfg.get("wrapper", {})
    perc = cfg.get("perception", {})
    return CommitBreakoutWrapper(
        enabled=bool(w.get("enabled", True) if enabled is None else enabled),
        commit_ms=float(w.get("commit_ms", 220)),
        breakout_commit_ms=float(w.get("breakout_commit_ms", 450)),
        clearance_trap_px=float(w.get("clearance_trap_px", 6.0)),
        momentum_weight=float(w.get("momentum_weight", 0.4)),
        stuck_motion_px=float(w.get("stuck_motion_px", 2.0)),
        stuck_frames=int(w.get("stuck_frames", 8)),
        contact_dilate_px=int(perc.get("contact_dilate_px", 8)),
        approach_id=approach_id,
    )
