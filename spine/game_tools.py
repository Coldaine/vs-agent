"""Typed, bounded game operations consumed by the LangGraph runtime.

Models never receive this module's I/O objects. They submit structured
proposals; ``Controller`` remains the sole writer of movement input.
"""

from __future__ import annotations

import math
import time
from pathlib import Path
from typing import Callable

import launch
import perceive
import reflex
from trace import EpisodeWriter


MODIFIER_KEYS = ("hyper", "hurry", "arcanas", "limit_break", "inverse", "endless")
MAX_CONTROL_WINDOW_S = 5.0


class SpineGameTools:
    def __init__(
        self,
        config: dict,
        io,
        controller,
        *,
        launch_module=launch,
        perception_module=perceive,
        writer_factory=EpisodeWriter,
        clock: Callable[[], float] = time.monotonic,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        self.cfg = config
        self.io = io
        self.controller = controller
        self.launch = launch_module
        self.perception = perception_module
        self.writer_factory = writer_factory
        self.clock = clock
        self.sleeper = sleeper
        self.run_id: str | None = None
        self.writer = None
        self.started_at: float | None = None
        self.last_options: list[str] = []
        self._observation_index = 0
        self._closed = False

    def prepare(self) -> dict:
        missing = [name for name in MODIFIER_KEYS if name not in self.cfg]
        if missing:
            return {
                "verified": False,
                "reason": "fixed modifier baseline is incomplete: " + ", ".join(missing),
            }

        self.neutralize()
        self.launch.to_stage_select(self.io, self.cfg)
        self.launch.start_run(self.io, self.cfg)
        self.run_id = f"run_{int(time.time() * 1000)}"
        self.writer = self.writer_factory(self.cfg["episodes_dir"], self.run_id)
        self.started_at = self.clock()
        self._closed = False
        return {"verified": True, "run_id": self.run_id}

    def observe(self) -> dict:
        self._require_active_run()
        frame = self.io.screenshot()
        screen_type = self.perception.screen_type(frame, self.cfg)
        summary = self.perception.state_summary(frame)
        self.last_options = (
            self.perception.read_options(frame) if screen_type == "LEVEL_UP" else []
        )
        name = f"observation-{self._observation_index:06d}.jpg"
        self._observation_index += 1
        self.writer.save_frame(
            self.perception.to_jpeg(frame), keyframe=True, name=name
        )
        image_path = str(Path(self.writer.dir, "keyframes", name).resolve())
        return {
            "screen_type": screen_type,
            "summary": summary,
            "options": list(self.last_options),
            "image_path": image_path,
        }

    def submit_direction(self, direction: str, latency_ms: float = 0.0) -> bool:
        return self.controller.submit_follower_proposal(direction, latency_ms)

    def control_window(self, seconds: float) -> dict:
        self._require_active_run()
        if seconds <= 0 or seconds > MAX_CONTROL_WINDOW_S:
            raise ValueError(
                f"control window must be >0 and <= {MAX_CONTROL_WINDOW_S} seconds"
            )
        tick_hz = float(self.cfg["tick_hz"])
        tick_count = max(1, math.ceil(seconds * tick_hz))
        tick_s = 1.0 / tick_hz
        evidence: list[str] = []
        try:
            for _ in range(tick_count):
                tick_started = self.clock()
                frame = self.io.screenshot()
                screen_type = self.perception.screen_type(frame, self.cfg)
                detections, player = self.perception.detect(frame)
                result = self.controller.tick(detections, player, screen_type)
                hud = self.perception.hud_state(frame)
                self.writer.log_tick(
                    hud["hp"],
                    hud["level"],
                    hud["timer"],
                    hud["inventory"],
                    reflex.threats_by_octant(detections, player),
                    reflex.gems_by_octant(detections, player),
                    result.rule_fired,
                    result.follower_latency_ms,
                    result.action,
                    result.rule_fired == "veto",
                )
                self.writer.save_frame(self.perception.to_jpeg(frame))
                evidence.append(f"tick:{len(evidence) + 1}")
                remaining = tick_s - (self.clock() - tick_started)
                if remaining > 0:
                    self.sleeper(remaining)
        except Exception:
            self.neutralize()
            raise
        return {"safe": True, "evidence": evidence}

    def select_level_up(self, option: int) -> dict:
        self._require_active_run()
        if not self.last_options:
            raise RuntimeError("no observed level-up options are available")
        self.launch.select_option(self.io, option, self.last_options)
        self.writer.log_planner(
            self.last_options,
            option,
            "selected by LangGraph leader through ChatGPT Pro OAuth",
            "",
        )
        return {"selected": option, "evidence": [f"level-up:{option}"]}

    def evaluate(self, goal: str, run_id: str) -> dict:
        self._require_active_run()
        if run_id != self.run_id:
            raise ValueError(f"run ID mismatch: expected {self.run_id}, got {run_id}")
        survived_s = self.clock() - float(self.started_at)
        invalid = False
        if not self._closed:
            self.writer.close(
                survived_s=round(survived_s, 1),
                level=self.perception.last_level,
                kills=self.perception.last_kills,
                invalid=invalid,
                prompt_hashes={
                    "leader": "chatgpt-oauth:gpt-5.6-luna",
                    "follower": "chatgpt-oauth:gpt-5.6-luna",
                },
            )
            self._closed = True
        target = float(self.cfg.get("goal_target_survival_s", 540.0))
        achieved = survived_s >= target and not invalid
        outcome_path = str(Path(self.writer.dir, "outcome.json").resolve())
        return {
            "status": "achieved" if achieved else "not_met",
            "reason": (
                f"survived {survived_s:.1f}s; target {target:.1f}s; "
                f"invalid={str(invalid).lower()}"
            ),
            "evidence": [outcome_path],
        }

    def neutralize(self) -> None:
        self.controller.neutralize()

    def close(self) -> None:
        self.neutralize()
        self.io.close()

    def _require_active_run(self) -> None:
        if self.run_id is None or self.writer is None or self.started_at is None:
            raise RuntimeError("game tools have no active prepared run")
