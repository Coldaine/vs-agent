from __future__ import annotations

import logging
import time
from typing import Any

from vs_harness.capture.window import build_capture
from vs_harness.config import load_config
from vs_harness.control.commit_breakout import build_wrapper
from vs_harness.control.input_injector import InputInjector
from vs_harness.control.kill_switch import KillSwitch
from vs_harness.planner.menu import handle_paused_ui
from vs_harness.planner.strategy import StrategyPlanner
from vs_harness.mode.detector import ModeDetector
from vs_harness.movers.registry import build_mover
from vs_harness.perception.factory import build_perception
from vs_harness.perception.masks import encode_rle
from vs_harness.sim.swarm_sim import SwarmSim
from vs_harness.trace.critique import _heading_entropy
from vs_harness.trace.writer import TraceWriter
from vs_harness.types import ScreenMode, WrapperMode

logger = logging.getLogger(__name__)

def run_episode(
    cfg: dict[str, Any],
    approach_id: str | None = None,
    wrapper_enabled: bool | None = None,
    seed: int | None = None,
    sim_seconds: float | None = None,
) -> dict[str, Any]:
    loop = cfg.get("loop", {})
    mode = loop.get("mode", "sim")
    seed = int(seed if seed is not None else loop.get("sim_seed", 0))
    duration = float(sim_seconds if sim_seconds is not None else loop.get("sim_seconds", 45.0))
    # Classic plan path: VLM pilot at ~2 Hz with sticky keys
    follower_hz = float(loop.get("follower_hz", 0.0))

    # Parked under sideInspiration: simulation only. Live I/O must go through
    # spine/controller.py + computer-control-mcp when/if pieces are adopted.
    if mode != "sim":
        raise RuntimeError(
            "vs_harness in sideInspiration is simulation-only "
            f"(got loop.mode={mode!r}). Set loop.mode: sim, or adopt live "
            "control through spine before enabling a live path."
        )

    sim = SwarmSim(seed=seed) if mode == "sim" else None
    capture = build_capture(cfg, sim=sim)
    perception = build_perception(cfg, sim=sim)

    # Attached-plan default: if approach unset and loop asks for vlm_follower, use fast_vlm
    if approach_id is None and loop.get("control_style") == "vlm_follower":
        approach_id = "fast_vlm"
        cfg = dict(cfg)
        cfg["mover"] = dict(cfg.get("mover", {}))
        cfg["mover"]["approach_id"] = "fast_vlm"
        # Sticky commit matches plan's "hold between ticks"
        if wrapper_enabled is None:
            cfg["wrapper"] = dict(cfg.get("wrapper", {}))
            cfg["wrapper"]["enabled"] = True
            cfg["wrapper"]["commit_ms"] = max(float(cfg["wrapper"].get("commit_ms", 220)), 1000.0 / max(follower_hz, 2.0))

    mover = build_mover(cfg, approach_id=approach_id)
    approach = mover.approach_id
    wrapper = build_wrapper(cfg, approach_id=approach, enabled=wrapper_enabled)
    planner = StrategyPlanner(cfg)
    detector = ModeDetector()

    injector = InputInjector(live=(mode == "live"))
    kill_key = str(cfg.get("host", {}).get("kill_switch_key", "F8"))
    kill = KillSwitch(kill_key) if mode == "live" else None

    trace_root = cfg.get("trace", {}).get("root", "runs")
    writer = TraceWriter(trace_root)
    save_masks = bool(cfg.get("trace", {}).get("save_masks_rle", True))

    writer.write(
        {
            "type": "run_start",
            "run_id": writer.run_id,
            "approach_id": approach,
            "wrapper_enabled": wrapper.enabled,
            "seed": seed,
            "mode": mode,
            "control_style": loop.get("control_style", "perception_mover"),
            "config_snapshot": {
                "mover": cfg.get("mover"),
                "wrapper": cfg.get("wrapper"),
                "openai": {
                    "base_url": cfg.get("openai", {}).get("base_url"),
                    "leader_model": cfg.get("openai", {}).get("leader_model"),
                    "follower_model": cfg.get("openai", {}).get("follower_model"),
                },
                "perception": {
                    k: v
                    for k, v in cfg.get("perception", {}).items()
                    if k not in ("enemy_prompts", "gem_prompts", "player_prompts")
                },
            },
        }
    )

    t0 = time.perf_counter()
    headings: list[str] = []
    breakouts = 0
    last_intent_mode = planner.intent.mode
    last_follower_t = 0.0
    last_cmd_heading = "HOLD"
    levelup_events = 0

    try:
        while True:
            now = time.perf_counter()
            elapsed = now - t0
            if kill is not None and kill.triggered:
                writer.write({"type": "kill_switch", "t": elapsed, "key": kill_key})
                break
            if mode == "sim":
                if sim is None or (not sim.alive) or sim.time_s >= duration:
                    break
            elif elapsed >= duration:
                break

            cap = capture.grab()
            screen = detector.detect(cap.frame_bgr)

            # Paused UI → planner chooses (attached plan planner loop)
            if screen in (ScreenMode.LEVELUP, ScreenMode.CHEST) and mode == "live":
                decision = handle_paused_ui(screen, cap.frame_bgr, planner, injector, now)
                levelup_events += 1
                writer.write({"type": "levelup", "t": elapsed, **decision})
                last_intent_mode = decision["intent"].get("mode", last_intent_mode)
                time.sleep(0.1)
                continue

            intent = planner.maybe_refresh(screen, cap.frame_bgr, now)
            if intent.mode != last_intent_mode:
                writer.write(
                    {
                        "type": "planner",
                        "t": elapsed,
                        "intent": intent.to_dict(),
                        "trigger": screen.value,
                    }
                )
                last_intent_mode = intent.mode

            if screen != ScreenMode.PLAYING:
                injector.release_all()
                if mode == "sim" and sim:
                    screen = ScreenMode.PLAYING
                else:
                    time.sleep(0.05)
                    continue

            # Optional pilot cadence (plan: ~2 Hz VLM); between ticks keep sticky keys
            if follower_hz > 0 and (now - last_follower_t) < (1.0 / follower_hz):
                injector.set_keys(_heading_keys(last_cmd_heading))
                if sim is not None:
                    sim.step(last_cmd_heading)
                headings.append(last_cmd_heading)
                writer.write(
                    {
                        "type": "tick",
                        "t": elapsed,
                        "screen_mode": screen.value,
                        "heading": last_cmd_heading,
                        "keys": sorted(_heading_keys(last_cmd_heading)),
                        "wrapper_mode": "committed",
                        "sticky": True,
                        "approach_id": approach,
                        "intent_mode": intent.mode,
                    }
                )
                target_fps = float(cfg.get("host", {}).get("target_fps", 30))
                time.sleep(max(0.0, (1.0 / target_fps) - (time.perf_counter() - now)))
                continue

            last_follower_t = now
            perc = perception.infer(cap.frame_bgr, cap.timestamp_s)
            proposal = mover.propose(perc, intent)
            cmd = wrapper.apply(proposal, perc, now)
            if cmd.wrapper_mode == WrapperMode.BREAKOUT:
                breakouts += 1

            injector.set_keys(cmd.keys)
            last_cmd_heading = cmd.heading
            if sim is not None:
                sim.step(cmd.heading)

            headings.append(cmd.heading)
            tick: dict[str, Any] = {
                "type": "tick",
                "t": elapsed,
                "screen_mode": screen.value,
                "heading": cmd.heading,
                "keys": sorted(cmd.keys),
                "wrapper_mode": cmd.wrapper_mode.value,
                "clearance": proposal.clearance_px,
                "urgency": cmd.urgency,
                "intent_mode": intent.mode,
                "perception_ms": perc.inference_ms,
                "approach_id": approach,
                "sticky": False,
            }
            if save_masks:
                tick["threat_rle"] = encode_rle(perc.threat_union)
            writer.write(tick)

            target_fps = float(cfg.get("host", {}).get("target_fps", 30))
            time.sleep(max(0.0, (1.0 / target_fps) - (time.perf_counter() - now)))

    finally:
        injector.release_all()
        capture.close()
        perception.close()
        if kill is not None:
            kill.stop()

    survive = sim.time_s if sim else (time.perf_counter() - t0)
    end = {
        "type": "run_end",
        "t": time.perf_counter() - t0,
        "alive": bool(sim.alive) if sim else True,
        "survive_s": float(survive),
        "hits": int(sim.hits) if sim else 0,
        "gems": int(sim.gems_collected) if sim else 0,
        "breakout_count": breakouts,
        "levelup_events": levelup_events,
        "mean_entropy": _heading_entropy(headings),
        "death_reason": (
            "kill_switch"
            if kill is not None and kill.triggered
            else ("hits" if sim and not sim.alive else "timeout")
        ),
        "approach_id": approach,
        "wrapper_enabled": wrapper.enabled,
        "run_id": writer.run_id,
        "trace_path": str(writer.path),
    }
    writer.write(end)
    writer.close()
    return end


def _heading_keys(heading: str) -> set[str]:
    from vs_harness.control.headings import heading_to_keys

    return heading_to_keys(heading)


def run_from_config_path(
    config_path: str,
    approach_id: str | None = None,
    wrapper_enabled: bool | None = None,
    seed: int | None = None,
) -> dict[str, Any]:
    cfg = load_config(config_path)
    return run_episode(
        cfg,
        approach_id=approach_id,
        wrapper_enabled=wrapper_enabled,
        seed=seed,
    )

