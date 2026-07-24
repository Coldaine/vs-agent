"""run.py - one episode of Vampire Survivors."""

from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import time

import yaml

from controller import Controller
from io_adapter import IOAdapter
from trace import EpisodeWriter, hash_prompt

import launch
import model_client
import perceive
import reflex


def pilot_loop(io, controller, cfg, stop, prompt_text, shared):
    """Async pilot: proposes directions without blocking the tick."""
    del cfg
    while not stop.is_set():
        try:
            frame = io.screenshot()
            state = perceive.state_summary(frame)
            t0 = time.monotonic()
            direction, speed = model_client.call_pilot(
                prompt_text, state, frame, shared["brief"])
            latency = (time.monotonic() - t0) * 1000
            if not controller.submit_pilot_proposal(direction, latency, speed):
                perceive.log_protocol_violation(direction)
        except Exception as error:
            print(f"[pilot] {error}", file=sys.stderr)
            time.sleep(0.1)


def _detect_for_tick(frame, reflex_only: bool):
    """G1 remains usable when the optional detector is unavailable."""
    try:
        return perceive.detect(frame)
    except (FileNotFoundError, ImportError, RuntimeError) as error:
        if not reflex_only:
            raise
        print(f"[reflex-only] detector unavailable: {error}", file=sys.stderr)
        return [], reflex.Detection(frame.width / 2.0, frame.height / 2.0, "player")


def run_episode(
    eval_mode: bool,
    reflex_only: bool = False,
    disable_planner: bool = False,
    pilot_prompt_path: str = "prompts/pilot.md",
    eval_seed: int | None = None,
):
    cfg = yaml.safe_load(open("spine/config.yaml", encoding="utf-8"))
    cfg["eval_seed"] = eval_seed if eval_mode else None
    io = IOAdapter(backend=os.environ.get("VS_IO_BACKEND", "auto"), config=cfg)
    controller = Controller(io, cfg)
    run_id = f"run_{int(time.time())}"
    ep = EpisodeWriter(cfg["episodes_dir"], run_id)
    pilot_prompt = open(pilot_prompt_path, encoding="utf-8").read() if not reflex_only else ""
    planner_prompt = open("prompts/planner.md", encoding="utf-8").read() if not disable_planner else ""
    shared = {"brief": "Early game: farm gems near open ground, orbit clockwise."}
    stop = threading.Event()
    latencies: list[float] = []
    start = time.monotonic()

    try:
        import nav

        launch.launch_game(cfg, io)
        if not nav.navigate_to_game(io, cfg):
            raise RuntimeError("nav agent finished without proving IN_GAME")

        if not reflex_only:
            pilot_thread = threading.Thread(
                target=pilot_loop,
                args=(io, controller, cfg, stop, pilot_prompt, shared),
                daemon=True,
            )
            pilot_thread.start()

        tick_s = 1.0 / cfg["tick_hz"]
        while True:
            tick_t0 = time.monotonic()
            frame = io.screenshot()
            screen_type = perceive.screen_type(frame, cfg)

            if screen_type == "LEVEL_UP":
                options = perceive.read_options(frame)
                if not disable_planner:
                    pick = model_client.call_planner(
                        planner_prompt, frame, options, shared["brief"])
                    ep.log_planner(
                        options, pick["pick"], pick["why"], pick["brief_update"])
                    shared["brief"] = pick["brief_update"]
                    launch.select_option(io, pick["pick"], options)
                else:
                    launch.select_option(io, 1, options)
                continue

            if screen_type in ("DEATH", "RUN_END"):
                break

            dets, player = _detect_for_tick(frame, reflex_only)
            result = controller.tick(dets, player, screen_type, strafe=reflex_only)
            if result.pilot_latency_ms is not None:
                latencies.append(result.pilot_latency_ms)
            st = perceive.hud_state(frame)
            ep.log_tick(
                st["hp"],
                st["level"],
                st["timer"],
                st["inventory"],
                reflex.threats_by_octant(dets, player),
                reflex.gems_by_octant(dets, player),
                result.rule_fired,
                result.pilot_latency_ms,
                result.action,
                result.rule_fired == "veto",
            )
            ep.save_frame(perceive.to_jpeg(frame))

            elapsed = time.monotonic() - tick_t0
            if elapsed < tick_s:
                time.sleep(tick_s - elapsed)

    finally:
        stop.set()
        controller.neutralize()
        io.close()
        survived = time.monotonic() - start
        p95 = sorted(latencies)[int(len(latencies) * 0.95)] if latencies else 0
        invalid = p95 > 800
        ep.close(
            survived_s=round(survived, 1),
            level=perceive.last_level,
            kills=perceive.last_kills,
            invalid=invalid,
            prompt_hashes={
                "pilot": hash_prompt(pilot_prompt_path),
                "planner": hash_prompt("prompts/planner.md"),
            },
        )
        print(json.dumps({
            "run_id": run_id,
            "eval_seed": eval_seed,
            "survived_s": round(survived, 1),
            "level": perceive.last_level,
            "kills": perceive.last_kills,
            "invalid": invalid,
            "p95_ms": p95,
        }))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed-set", default=None)
    parser.add_argument("--eval-seed", type=int, default=None)
    parser.add_argument("--reflex-only", action="store_true")
    parser.add_argument("--disable-planner", "--disable-leader", dest="disable_planner", action="store_true")
    parser.add_argument("--pilot-prompt", default="prompts/pilot.md")
    args = parser.parse_args()
    run_episode(
        eval_mode=args.seed_set == "eval",
        reflex_only=args.reflex_only,
        disable_planner=args.disable_planner,
        pilot_prompt_path=args.pilot_prompt,
        eval_seed=args.eval_seed,
    )
