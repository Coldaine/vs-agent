"""review.py — post-run analysis. Runs sub-agents in FRESH contexts,
writes failures.jsonl, appends gallery frames. Never feeds raw traces
to the builder's context.

Usage: python spine/review.py episodes/run_<n>
"""

from __future__ import annotations
import json, os, sys, glob
import model_client


# --- directive generation from controller telemetry (trace_spec.md) ---
def generate_directive(states: list[dict]) -> str:
    """Override-rate spike detection: any 60s window where
    (veto+stale+dither)/ticks exceeds 2x the run median."""
    overrides = [(s["t"], s["rule_fired"] != "clean") for s in states]
    if not overrides:
        return "full autopsy"
    median_rate = sum(o for _, o in overrides) / len(overrides)
    window = 60.0
    worst, worst_rate = None, 0.0
    for t0, _ in overrides:
        win = [o for t, o in overrides if t0 <= t < t0 + window]
        if len(win) < 10:
            continue
        rate = sum(win) / len(win)
        if rate > worst_rate:
            worst, worst_rate = t0, rate
    if worst is not None and median_rate > 0 and worst_rate > 2 * median_rate:
        return (f"Override rate spiked to {worst_rate:.0%} during "
                f"t={worst:.0f}-{worst+window:.0f} (run median "
                f"{median_rate:.0%}). Inspect that window: was the "
                "pilot wrong, or was the reflex layer over-sensitive?")
    return "full autopsy"


def assemble_packet(run_dir: str) -> dict:
    states = [json.loads(l) for l in open(os.path.join(run_dir, "states.jsonl"))]
    outcome = json.load(open(os.path.join(run_dir, "outcome.json")))
    t_end = outcome["survived_s"]
    packet_states = ([s for s in states if s["t"] % 5 < 0.6]
                     + [s for s in states if s["t"] > t_end - 60])
    keyframes = sorted(glob.glob(os.path.join(run_dir, "keyframes", "*.jpg")))
    histogram = {}
    if os.path.exists("failures.jsonl"):
        for l in open("failures.jsonl"):
            ft = json.loads(l).get("dominant_failure_type")
            if ft:
                histogram[ft] = histogram.get(ft, 0) + 1
    prompts = {
        "pilot": open("prompts/pilot.md", encoding="utf-8").read(),
        "planner": open("prompts/planner.md", encoding="utf-8").read(),
    }
    return {"states": packet_states, "keyframes": keyframes,
            "outcome": outcome, "histogram": histogram,
            "directive": generate_directive(states), "prompts": prompts}


def review_run(run_dir: str):
    packet = assemble_packet(run_dir)
    autopsy_prompt = open("prompts/review_autopsy.md").read().replace(
        "{{INSPECTION_DIRECTIVE}}", packet["directive"])
    build_prompt = open("prompts/review_build.md").read()

    autopsy = model_client.call_subagent(
        autopsy_prompt, packet, keyframes=packet["keyframes"])
    planner_path = os.path.join(run_dir, "planner.jsonl")
    if not os.path.exists(planner_path):
        planner_path = os.path.join(run_dir, "leader.jsonl")
    planner_log = [json.loads(l) for l in open(planner_path)] \
        if os.path.exists(planner_path) else []
    build = model_client.call_subagent(
        build_prompt, {"planner_log": planner_log, "outcome": packet["outcome"]})

    with open("failures.jsonl", "a") as f:
        f.write(json.dumps({"run": run_dir, **autopsy}) + "\n")
        f.write(json.dumps({"run": run_dir, "build_audit": build}) + "\n")

    # grow the failure gallery (trace_spec.md)
    os.makedirs("eval_set/gallery", exist_ok=True)
    for err in autopsy.get("follower_errors", []):
        model_client.export_gallery_frames(run_dir, err, "eval_set/gallery")

    print(json.dumps({"run": run_dir,
                      "cause": autopsy.get("cause_of_death"),
                      "directive": packet["directive"]}))


if __name__ == "__main__":
    review_run(sys.argv[1])

