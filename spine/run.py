"""run.py — one episode of Vampire Survivors.

Usage:
  python spine/run.py                  # one episode
  python spine/run.py --seed-set eval  # eval episode (fixed conditions)

Structure: perception (YOLO+OCR, builder's seam) -> follower proposal
(async, OpenAI-compatible endpoint) -> controller (deterministic) ->
trace. Level-up screens hand off to the leader. Every exit path
neutralizes the controller — no runaway held inputs overnight.
"""

from __future__ import annotations
import argparse, json, os, sys, time, threading
import yaml
from io_adapter import IOAdapter
from controller import Controller
from trace import EpisodeWriter, hash_prompt
import reflex
import launch
import model_client          # builder: OpenAI-compatible client wrapper
import perceive              # builder: YOLO detections + OCR state


def follower_loop(io, controller, cfg, stop, prompt_text, shared):
    """Async follower: proposes directions without blocking the tick.
    Reads shared['brief'] EVERY iteration so leader brief_updates
    propagate — passing brief by value here was bug #1 found in audit."""
    while not stop.is_set():
        try:
            frame = io.screenshot()
            state = perceive.state_summary(frame)
            t0 = time.monotonic()
            direction = model_client.call_follower(
                prompt_text, state, frame, shared["brief"])
            latency = (time.monotonic() - t0) * 1000
            if not controller.submit_follower_proposal(direction, latency):
                perceive.log_protocol_violation(direction)
        except Exception as e:
            print(f"[follower] {e}", file=sys.stderr)
            time.sleep(0.1)


def run_episode(eval_mode: bool):
    cfg = yaml.safe_load(open("spine/config.yaml"))
    io = IOAdapter(backend=os.environ.get("VS_IO_BACKEND", "auto"), config=cfg)
    controller = Controller(io, cfg)
    run_id = f"run_{int(time.time())}"
    ep = EpisodeWriter(cfg["episodes_dir"], run_id)
    follower_prompt = open("prompts/follower.md").read()
    leader_prompt = open("prompts/leader.md").read()
    # mutable cell so the leader's brief_update reaches the follower
    shared = {"brief": "Early game: farm gems near open ground, orbit clockwise."}
    stop = threading.Event()
    latencies, start = [], time.monotonic()

    try:
        launch.to_stage_select(io, cfg)          # launch + menu macro
        launch.start_run(io, cfg)
        fw = threading.Thread(target=follower_loop,
                              args=(io, controller, cfg, stop,
                                    follower_prompt, shared), daemon=True)
        fw.start()

        tick_s = 1.0 / cfg["tick_hz"]
        while True:
            tick_t0 = time.monotonic()
            frame = io.screenshot()
            screen_type = perceive.screen_type(frame, cfg)

            if screen_type == "LEVEL_UP":
                options = perceive.read_options(frame)
                pick = model_client.call_leader(leader_prompt, frame,
                                                options, shared["brief"])
                ep.log_leader(options, pick["pick"], pick["why"],
                              pick["brief_update"])
                shared["brief"] = pick["brief_update"]
                launch.select_option(io, pick["pick"], options)
                continue

            if screen_type in ("DEATH", "RUN_END"):
                break

            dets, player = perceive.detect(frame)
            result = controller.tick(dets, player, screen_type)
            if result.follower_latency_ms:
                latencies.append(result.follower_latency_ms)
            st = perceive.hud_state(frame)
            ep.log_tick(st["hp"], st["level"], st["timer"],
                        st["inventory"],
                        reflex.threats_by_octant(dets, player),
                        reflex.gems_by_octant(dets, player),
                        result.rule_fired, result.follower_latency_ms,
                        result.action, result.rule_fired == "veto")
            ep.save_frame(perceive.to_jpeg(frame))

            elapsed = time.monotonic() - tick_t0
            if elapsed < tick_s:
                time.sleep(tick_s - elapsed)

    finally:
        stop.set()
        controller.neutralize()          # every exit path, no exceptions
        survived = time.monotonic() - start
        p95 = (sorted(latencies)[int(len(latencies) * .95)]
               if latencies else 0)
        invalid = p95 > 800
        ep.close(survived_s=round(survived, 1),
                 level=perceive.last_level, kills=perceive.last_kills,
                 invalid=invalid,
                 prompt_hashes={"follower": hash_prompt("prompts/follower.md"),
                                "leader": hash_prompt("prompts/leader.md")})
        print(json.dumps({"run_id": run_id, "survived_s": survived,
                          "invalid": invalid, "p95_ms": p95}))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed-set", default=None)
    run_episode(eval_mode=ap.parse_args().seed_set == "eval")
