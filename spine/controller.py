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
    speed: float
    rule_fired: str          # clean | veto | stale | dither | level_up
    follower_latency_ms: float | None
    degraded: bool


class Controller:
    def __init__(self, io: IOAdapter, config: dict):
        self.io = io
        self.cfg = config
        self._last_pilot_proposal: tuple[float, str, float] | None = None
        self._current_heading: str = "N"
        self._current_speed: float = 1.0
        self._last_change_t: float = 0.0

    # --- proposals enter here ---
    def submit_pilot_proposal(self, direction: str, latency_ms: float, speed: float = 1.0) -> bool:
        if direction not in DIRECTIONS:
            return False                     # protocol violation, logged by caller
        self._last_pilot_proposal = (time.monotonic(), direction, speed)
        self._last_latency = latency_ms
        return True

    # --- the tick, per docs/controller.md ---
    def tick(self, dets: list[reflex.Detection], player: reflex.Detection,
             screen_type: str, strafe: bool = False) -> TickResult:
        if screen_type == "LEVEL_UP":
            self.io.hold_direction("HOLD")
            return TickResult("HOLD", 1.0, "level_up", None, False)

        proposal, speed, latency = self._fresh_proposal()
        rule = "clean"

        # 3. VETO
        if proposal and reflex.veto_check(
                proposal, dets, player, self.cfg["collision_radius_px"]):
            proposal = reflex.escape_vector(dets, player, self.cfg["escape_vector_k"])
            speed = 1.0  # Panic run
            rule = "veto"

        # 4. STALE / REFLEX-ONLY
        if proposal is None:
            threat = reflex.nearest_threat(dets, player)
            if threat and threat[0] < self.cfg["collision_radius_px"] * 2.0:
                proposal = reflex.escape_vector(dets, player, self.cfg["escape_vector_k"])
                speed = 1.0
                rule = "veto" if strafe else "stale"
            elif strafe:
                # G1 Blind Strafe: left/right oscillation
                proposal = "E" if (int(time.monotonic()) % 6) < 3 else "W"
                speed = 1.0
                rule = "clean"
            else:
                proposal = self._current_heading      # keep drifting
                speed = self._current_speed
                rule = "stale"

        # 5. DITHER
        if (proposal != self._current_heading
                and rule == "clean"
                and (time.monotonic() - self._last_change_t) * 1000 < self.cfg["dither_ms"]
                and self._is_reversal(proposal)):
            proposal = self._current_heading
            speed = self._current_speed
            rule = "dither"

        # 6. COMMIT
        self.io.hold_direction(proposal, speed)
        if proposal != self._current_heading or speed != self._current_speed:
            self._current_heading = proposal
            self._current_speed = speed
            self._last_change_t = time.monotonic()

        return TickResult(proposal, speed, rule, latency, degraded=(rule == "stale"))

    def _fresh_proposal(self) -> tuple[str | None, float, float | None]:
        if self._last_pilot_proposal is None:
            return None, 1.0, None
        t, direction, speed = self._last_pilot_proposal
        age_ms = (time.monotonic() - t) * 1000
        if age_ms > self.cfg["staleness_ms"]:
            return None, 1.0, getattr(self, "_last_latency", None)
        return direction, speed, getattr(self, "_last_latency", None)

    def _is_reversal(self, proposal: str) -> bool:
        if proposal not in reflex.OCTANT_VEC or self._current_heading not in reflex.OCTANT_VEC:
            return False
        a, b = reflex.OCTANT_VEC[proposal], reflex.OCTANT_VEC[self._current_heading]
        return a[0] * b[0] + a[1] * b[1] < 0          # >90 deg reversal

    def neutralize(self) -> None:
        self.io.neutralize()
