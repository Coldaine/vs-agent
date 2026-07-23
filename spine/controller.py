"""controller.py — deterministic arbiter FSM. Spec: docs/controller.md.

The ONLY component that writes input (via io_adapter). Models propose;
the controller disposes. Every tick logs which rule fired so the
review/theorist pipeline gets clean attribution.
"""

from __future__ import annotations
import time
from dataclasses import dataclass, field
from io_adapter import IOAdapter, DIRECTIONS
import reflex


@dataclass
class TickResult:
    action: str
    rule_fired: str          # clean | veto | stale | dither | level_up
    follower_latency_ms: float | None
    degraded: bool


class Controller:
    def __init__(self, io: IOAdapter, config: dict):
        self.io = io
        self.cfg = config
        self._last_follower_proposal: tuple[float, str] | None = None
        self._current_heading: str = "N"
        self._last_change_t: float = 0.0

    # --- proposals enter here ---
    def submit_follower_proposal(self, direction: str, latency_ms: float) -> bool:
        if direction not in DIRECTIONS:
            return False                     # protocol violation, logged by caller
        self._last_follower_proposal = (time.monotonic(), direction)
        self._last_latency = latency_ms
        return True

    # --- the tick, per docs/controller.md ---
    def tick(self, dets: list[reflex.Detection], player: reflex.Detection,
             screen_type: str) -> TickResult:
        if screen_type == "LEVEL_UP":
            self.io.hold_direction("HOLD")
            return TickResult("HOLD", "level_up", None, False)

        proposal, latency = self._fresh_proposal()
        rule = "clean"

        # 3. VETO
        if proposal and reflex.veto_check(
                proposal, dets, player, self.cfg["collision_radius_px"]):
            proposal = reflex.escape_vector(dets, player, self.cfg["escape_vector_k"])
            rule = "veto"

        # 4. STALE
        if proposal is None:
            threat = reflex.nearest_threat(dets, player)
            if threat and threat[0] < self.cfg["collision_radius_px"] * 1.5:
                proposal = reflex.escape_vector(dets, player, self.cfg["escape_vector_k"])
            else:
                proposal = self._current_heading      # keep drifting
            rule = "stale"

        # 5. DITHER
        if (proposal != self._current_heading
                and rule == "clean"
                and (time.monotonic() - self._last_change_t) * 1000 < self.cfg["dither_ms"]
                and self._is_reversal(proposal)):
            proposal = self._current_heading
            rule = "dither"

        # 6. COMMIT
        self.io.hold_direction(proposal)
        if proposal != self._current_heading:
            self._current_heading = proposal
            self._last_change_t = time.monotonic()

        return TickResult(proposal, rule, latency, degraded=(rule == "stale"))

    def _fresh_proposal(self) -> tuple[str | None, float | None]:
        if self._last_follower_proposal is None:
            return None, None
        t, direction = self._last_follower_proposal
        age_ms = (time.monotonic() - t) * 1000
        if age_ms > self.cfg["staleness_ms"]:
            return None, getattr(self, "_last_latency", None)
        return direction, getattr(self, "_last_latency", None)

    def _is_reversal(self, proposal: str) -> bool:
        if proposal not in reflex.OCTANT_VEC or self._current_heading not in reflex.OCTANT_VEC:
            return False
        a, b = reflex.OCTANT_VEC[proposal], reflex.OCTANT_VEC[self._current_heading]
        return a[0] * b[0] + a[1] * b[1] < 0          # >90 deg reversal

    def neutralize(self) -> None:
        self.io.neutralize()
