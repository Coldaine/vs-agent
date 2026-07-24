from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

import numpy as np

from vs_harness.config import load_config
from vs_harness.loop.harness import run_episode
from vs_harness.paths import default_config
from vs_harness.perception.factory import PERCEPTION_BACKENDS, build_perception
from vs_harness.sim.swarm_sim import SwarmSim


def bench_perception(cfg: dict[str, Any], backend: str, frames: int = 40, seed: int = 0) -> dict[str, Any]:
    if frames <= 0:
        raise ValueError("frames must be > 0")
    cfg = dict(cfg)
    cfg["perception"] = dict(cfg.get("perception", {}))
    cfg["perception"]["backend"] = backend
    sim = SwarmSim(seed=seed)
    perc = build_perception(cfg, sim=sim)
    times = []
    ious = []
    try:
        for i in range(frames):
            sim.step("NE" if i % 2 == 0 else "W")
            frame = sim.render()
            gt, _, _, _ = sim.ground_truth_masks()
            t0 = time.perf_counter()
            out = perc.infer(frame, time.perf_counter())
            times.append((time.perf_counter() - t0) * 1000)
            inter = np.logical_and(out.threat_union, gt).sum()
            union = np.logical_or(out.threat_union, gt).sum()
            ious.append(float(inter / union) if union else 1.0)
    finally:
        perc.close()
    arr = np.array(times)
    return {
        "backend": backend,
        "resolved_backend": perc.name,
        "frames": frames,
        "mean_ms": float(arr.mean()),
        "p50_ms": float(np.median(arr)),
        "p95_ms": float(np.percentile(arr, 95)),
        "fps_est": float(1000.0 / max(arr.mean(), 1e-6)),
        "mean_threat_iou_vs_sim_gt": float(np.mean(ious)),
    }


def run_perception_bakeoff(cfg: dict[str, Any]) -> dict[str, Any]:
    pb = cfg.get("perception_bakeoff", {})
    backends = list(pb.get("backends") or ["mock", "color_heuristic", "optical_flow"])
    frames = int(pb.get("frames", 40))
    seeds = list(pb.get("seeds", [1, 2]))
    if not seeds:
        raise ValueError("perception_bakeoff.seeds must be non-empty")
    if frames <= 0:
        raise ValueError("perception_bakeoff.frames must be > 0")
    mover = pb.get("mover_for_episode", "sector_density")
    episode_s = float(pb.get("episode_seconds", 6.0))
    report_path = Path(pb.get("report_path", "runs/perception_bakeoff_report.json"))
    report_path.parent.mkdir(parents=True, exist_ok=True)

    benches = []
    episodes = []
    for backend in backends:
        # Skip heavy optional backends if they fall back silently? still bench mock fallback
        b = bench_perception(cfg, backend, frames=frames, seed=seeds[0])
        benches.append(b)
        print(
            f"[perc-bench] {backend}→{b['resolved_backend']} "
            f"{b['mean_ms']:.2f}ms (~{b['fps_est']:.0f} fps) iou={b['mean_threat_iou_vs_sim_gt']:.3f}"
        )
        for seed in seeds:
            ecfg = dict(cfg)
            ecfg["perception"] = dict(cfg.get("perception", {}))
            ecfg["perception"]["backend"] = backend
            ecfg["loop"] = dict(cfg.get("loop", {}))
            ecfg["loop"]["mode"] = "sim"
            ecfg["loop"]["sim_seconds"] = episode_s
            ecfg["mover"] = dict(cfg.get("mover", {}))
            ecfg["mover"]["approach_id"] = mover
            end = run_episode(ecfg, approach_id=mover, wrapper_enabled=True, seed=int(seed), sim_seconds=episode_s)
            episodes.append(
                {
                    "backend": backend,
                    "seed": seed,
                    "survive_s": end.get("survive_s"),
                    "hits": end.get("hits"),
                    "gems": end.get("gems"),
                    "mean_entropy": end.get("mean_entropy"),
                    "run_id": end.get("run_id"),
                }
            )
            print(
                f"[perc-ep] {backend} seed={seed} survive={end['survive_s']:.2f}s hits={end['hits']}"
            )

    report = {
        "available_backends": list(PERCEPTION_BACKENDS),
        "benchmarks": benches,
        "episodes": episodes,
        "note": "On this host, sam3/yolo_world may fall back to mock if packages missing.",
    }
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Wrote {report_path}")
    return report


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Perception backend bakeoff")
    parser.add_argument("--config", default=default_config("perception_bakeoff.yaml"))
    args = parser.parse_args(argv)
    cfg = load_config(args.config)
    run_perception_bakeoff(cfg)


if __name__ == "__main__":
    main()
