"""coordinator.py — G3 eval coordinator.

Paces a baseline pilot prompt and a candidate pilot prompt over a fixed
set of eval episodes (Mad Forest + Antonio, config seed list), parses each
episode's outcome from run.py, and appends the survival_time and kills
deltas to experiments.log. Depends on G0-G2 (a launchable, perceiving
episode). This file only paces and compares — no Loop M/C logic lives here.

Usage:
  python spine/coordinator.py --candidate prompts/pilot_candidate.md
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time

import yaml

CONFIG_PATH = "spine/config.yaml"


def _parse_outcome(stdout: str) -> dict | None:
    """run.py prints a single JSON summary line; find the last one."""
    for line in reversed(stdout.splitlines()):
        line = line.strip()
        if line.startswith("{") and '"run_id"' in line:
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                return None
    return None


def run_batch(prompt_path: str, episodes: int, timeout_s: int) -> list[dict]:
    """Run `episodes` eval episodes with the given pilot prompt."""
    results: list[dict] = []
    for i in range(episodes):
        print(f"[coordinator] {prompt_path}: episode {i + 1}/{episodes}")
        try:
            proc = subprocess.run(
                [sys.executable, "spine/run.py", "--seed-set", "eval",
                 "--pilot-prompt", prompt_path],
                capture_output=True, text=True, timeout=timeout_s)
        except subprocess.TimeoutExpired:
            print(f"[coordinator] episode {i + 1} timed out after {timeout_s}s")
            continue
        outcome = _parse_outcome(proc.stdout)
        if outcome is None:
            print(f"[coordinator] could not parse outcome for episode {i + 1}")
            if proc.stderr:
                print(proc.stderr[-500:], file=sys.stderr)
            continue
        if outcome.get("invalid"):
            print(f"[coordinator] episode {i + 1} invalid (latency); skipping")
            continue
        results.append(outcome)
    return results


def _mean(rows: list[dict], key: str) -> float:
    vals = [float(r.get(key) or 0) for r in rows]
    return sum(vals) / len(vals) if vals else 0.0


def coordinate(candidate_prompt: str,
               baseline_prompt: str = "prompts/pilot.md") -> dict:
    cfg = yaml.safe_load(open(CONFIG_PATH))
    episodes = int(cfg.get("eval_episodes", len(cfg.get("eval_seeds", [1, 2]))))
    timeout_s = int(cfg.get("eval_episode_timeout_s", 1800))

    baseline = run_batch(baseline_prompt, episodes, timeout_s)
    candidate = run_batch(candidate_prompt, episodes, timeout_s)

    summary = {
        "t": time.time(),
        "baseline_prompt": baseline_prompt,
        "candidate_prompt": candidate_prompt,
        "episodes": episodes,
        "baseline_valid": len(baseline),
        "candidate_valid": len(candidate),
        "survival_delta_s": round(
            _mean(candidate, "survived_s") - _mean(baseline, "survived_s"), 1),
        "kills_delta": round(
            _mean(candidate, "kills") - _mean(baseline, "kills"), 1),
    }

    log_path = cfg.get("experiments_log", "experiments.log")
    with open(log_path, "a") as f:
        f.write(json.dumps({"eval_batch": summary}) + "\n")
    print(json.dumps(summary, indent=2))
    return summary


if __name__ == "__main__":
    ap = argparse.ArgumentParser(
        description="G3 eval coordinator: baseline vs candidate pilot prompt.")
    ap.add_argument("--candidate", required=True,
                    help="Path to the candidate pilot prompt.")
    ap.add_argument("--baseline", default="prompts/pilot.md",
                    help="Path to the baseline pilot prompt.")
    args = ap.parse_args()
    coordinate(args.candidate, args.baseline)
