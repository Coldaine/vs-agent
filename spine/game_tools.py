"""Typed, bounded game operations consumed by the LangGraph runtime.

Models never receive this module's I/O objects. They submit structured
proposals; ``Controller`` remains the sole writer of movement input.
Menu entry is vision-led: prepare only launches/focuses; the leader proposes
menu actions that this module executes.
"""

from __future__ import annotations

import math
import time
from pathlib import Path
from typing import Callable

import launch
import perceive
import reflex
from capture_transform import (
    CalibrationError,
    assert_capture_contract,
    modifier_baseline,
)
from trace import EpisodeWriter


MODIFIER_KEYS = ("hyper", "hurry", "arcanas", "limit_break", "inverse", "endless")
MAX_CONTROL_WINDOW_S = 5.0
MENU_ACTIONS = ("up", "down", "left", "right", "confirm", "esc", "start")
MENU_GUESSES = {
    "WARNING",
    "TITLE",
    "MAIN_MENU",
    "CHARACTER_SELECT",
    "STAGE_SELECT",
    "UNKNOWN",
}


class SpineGameTools:
    def __init__(
        self,
        config: dict,
        io,
        controller,
        *,
        attach: bool = False,
        entry_only: bool = False,
        launch_module=launch,
        perception_module=perceive,
        writer_factory=EpisodeWriter,
        clock: Callable[[], float] = time.monotonic,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        self.cfg = config
        self.io = io
        self.controller = controller
        self.attach = attach
        self.entry_only = entry_only
        self.launch = launch_module
        self.perception = perception_module
        self.writer_factory = writer_factory
        self.clock = clock
        self.sleeper = sleeper
        self.run_id: str | None = None
        self.writer = None
        self.started_at: float | None = None
        self.in_game = False
        self.last_options: list[str] = []
        self.modifiers: dict[str, bool] | None = None
        self._observation_index = 0
        self._closed = False

    def prepare(self) -> dict:
        try:
            self.modifiers = modifier_baseline(self.cfg)
        except CalibrationError as error:
            return {"verified": False, "reason": str(error)}

        self.neutralize()
        attach_info = None
        if self.attach:
            attach_info = self.launch.attach_live(self.io, self.cfg)
            self.in_game = True
            self.started_at = self.clock()
        else:
            # Plumbing only: launch/focus. Vision leader navigates menus.
            self.launch.launch_game(self.cfg, self.io)
            self.in_game = False
            self.started_at = None

        try:
            self.sleeper(float(self.cfg.get("capture_contract_wait_s", 3.0)))
            frame = self.io.screenshot()
            assert_capture_contract(self.cfg, (frame.width, frame.height))
        except CalibrationError as error:
            self.neutralize()
            return {
                "verified": False,
                "reason": (
                    f"{error}. Set Vampire Survivors to fullscreen on the "
                    "capture monitor, leave the desktop idle, then recalibrate "
                    "capture_calibration_resolution if the native size changed."
                ),
            }
        except Exception as error:
            self.neutralize()
            return {
                "verified": False,
                "reason": f"capture contract check failed: {error}",
            }

        self.run_id = f"run_{int(time.time() * 1000)}"
        self.writer = self.writer_factory(self.cfg["episodes_dir"], self.run_id)
        self._closed = False
        self._observation_index = 0
        result = {
            "verified": True,
            "run_id": self.run_id,
            "modifiers": dict(self.modifiers),
            "attached": bool(self.attach),
            "entry_only": bool(self.entry_only),
            "menu_steps_budget": int(self.cfg.get("menu_steps_budget", 40)),
            "capture_resolution": [frame.width, frame.height],
            "eval_contract": {
                "character": self.cfg.get("character"),
                "stage": self.cfg.get("stage"),
                "modifiers": dict(self.modifiers),
            },
        }
        if attach_info is not None:
            result["attach_state"] = attach_info["state"]
        return result

    def observe(self) -> dict:
        self._require_active_run()
        frame = self.io.screenshot()
        screen_type, screen_guess, ocr_hint = self._classify_observation(frame)
        if screen_type in {"PLAY", "LEVEL_UP"}:
            self._enter_game()
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
            "screen_guess": screen_guess,
            "ocr_hint": ocr_hint,
            "summary": summary,
            "options": list(self.last_options),
            "image_path": image_path,
            "in_game": self.in_game,
            "hints_are_non_authoritative": True,
        }

    def menu_action(
        self,
        action: str,
        click: list[int] | tuple[int, int] | None = None,
    ) -> dict:
        """Execute one bounded menu input proposed by the vision leader."""
        self._require_active_run()
        action_key = str(action or "").lower()
        try:
            if click is not None and action_key != "click":
                raise ValueError("click coordinates require action='click'")
            if action_key == "click":
                if click is None:
                    raise ValueError("action='click' requires [x, y] coordinates")
                if len(click) != 2:
                    raise ValueError("click must be [x, y] frame coordinates")
                frame = self.io.screenshot()
                x, y = int(click[0]), int(click[1])
                if not (0 <= x < frame.width and 0 <= y < frame.height):
                    raise ValueError(
                        f"click [{x}, {y}] is outside captured frame "
                        f"{frame.width}x{frame.height}"
                    )
                self.io.click_frame(x, y)
                evidence = f"menu:click:{x},{y}"
            elif action_key in MENU_ACTIONS:
                self.io.menu_navigate(action_key)
                evidence = f"menu:{action_key}"
            else:
                raise ValueError(
                    f"unsupported menu action {action!r}; "
                    f"expected one of {MENU_ACTIONS} or a click"
                )
            self.sleeper(float(self.cfg.get("menu_action_settle_s", 0.35)))
        except Exception:
            self.neutralize()
            raise
        return {"ok": True, "evidence": [evidence]}

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
        if isinstance(option, bool) or not 1 <= option <= len(self.last_options):
            self.neutralize()
            raise ValueError(
                f"level-up option must be between 1 and {len(self.last_options)}, "
                f"got {option!r}"
            )
        try:
            self.launch.select_option(self.io, option, self.last_options)
        except Exception:
            self.neutralize()
            raise
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
        if self.entry_only:
            return self.evaluate_entry(run_id)
        if self.started_at is None:
            survived_s = 0.0
        else:
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

    def evaluate_entry(self, run_id: str) -> dict:
        """Success = vision reached in-game; used by G0 / --entry-only."""
        self._require_active_run()
        if run_id != self.run_id:
            raise ValueError(f"run ID mismatch: expected {self.run_id}, got {run_id}")
        self._enter_game()
        if not self._closed:
            self.writer.close(
                survived_s=0.0,
                level=self.perception.last_level,
                kills=self.perception.last_kills,
                invalid=False,
                prompt_hashes={
                    "leader": "chatgpt-oauth:gpt-5.6-luna",
                    "follower": "chatgpt-oauth:gpt-5.6-luna",
                },
            )
            self._closed = True
        outcome_path = str(Path(self.writer.dir, "outcome.json").resolve())
        return {
            "status": "achieved" if self.in_game else "not_met",
            "reason": "vision reached in-game HUD under fixed eval contract",
            "evidence": [outcome_path],
        }

    def mark_in_game(self) -> None:
        """Vision leader asserted in-run state; start survival clock."""
        self._enter_game()

    def neutralize(self) -> None:
        self.controller.neutralize()

    def close(self) -> None:
        self.neutralize()
        self.io.close()

    def _enter_game(self) -> None:
        if not self.in_game:
            self.in_game = True
            self.started_at = self.clock()

    def _classify_observation(self, frame) -> tuple[str, str, str]:
        """Return (screen_type, screen_guess, ocr_hint).

        OCR / classify_screen are non-authoritative hints for the leader.
        Routing only needs a coarse family: MENU vs in-run states.
        """
        ocr_hint = ""
        try:
            ocr_hint = " ".join(self.io.ocr().upper().split())[:300]
        except Exception as error:
            ocr_hint = f"ocr unavailable: {error}"

        screen_guess = "UNKNOWN"
        try:
            screen_guess, guess_text = self.launch.classify_screen(self.io)
            if guess_text and not ocr_hint.startswith("OCR UNAVAILABLE"):
                ocr_hint = " ".join(guess_text.split())[:300]
        except Exception:
            screen_guess = "UNKNOWN"

        if screen_guess in MENU_GUESSES:
            return "MENU", screen_guess, ocr_hint

        play_type = self.perception.screen_type(frame, self.cfg)
        if play_type in {"LEVEL_UP", "DEATH", "RUN_END"}:
            return play_type, screen_guess, ocr_hint
        if screen_guess == "LEVEL_UP":
            return "LEVEL_UP", screen_guess, ocr_hint
        if screen_guess == "IN_GAME":
            return "PLAY", screen_guess, ocr_hint
        # Prefer vision over blocking: unknown pre-run frames go to MENU.
        return "MENU", screen_guess, ocr_hint

    def _require_active_run(self) -> None:
        if self.run_id is None or self.writer is None:
            raise RuntimeError("game tools have no active prepared run")
