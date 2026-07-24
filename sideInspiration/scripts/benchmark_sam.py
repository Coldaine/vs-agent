#!/usr/bin/env python3
"""Benchmark SAM 3.1 / mock perception FPS on the current machine."""

from __future__ import annotations

import argparse
import time

import numpy as np

from vs_harness.config import load_config
from vs_harness.perception.factory import build_perception
from vs_harness.sim.swarm_sim import SwarmSim


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/default.yaml")
    parser.add_argument("--backend", choices=["mock", "sam3"], default=None)
    parser.add_argument("--frames", type=int, default=50)
    args = parser.parse_args()

    cfg = load_config(args.config)
    if args.backend:
        cfg.setdefault("perception", {})["backend"] = args.backend

    sim = SwarmSim(seed=0)
    perc = build_perception(cfg, sim=sim)
    print(f"backend={perc.name} frames={args.frames}")

    times = []
    for i in range(args.frames):
        sim.step("NE" if i % 2 == 0 else "SW")
        frame = sim.render()
        t0 = time.perf_counter()
        out = perc.infer(frame, time.perf_counter())
        times.append(out.inference_ms)
    arr = np.array(times)
    print(
        f"inference_ms: mean={arr.mean():.2f} p50={np.median(arr):.2f} "
        f"p95={np.percentile(arr, 95):.2f} fps~={1000.0 / max(arr.mean(), 1e-6):.1f}"
    )


if __name__ == "__main__":
    main()
