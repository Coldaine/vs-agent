from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from vs_harness.config import load_config
from vs_harness.loop.harness import run_episode
from vs_harness.movers.registry import APPROACH_IDS
from vs_harness.trace.critique import critique_run


def run_bakeoff(cfg: dict[str, Any]) -> dict[str, Any]:
    b = cfg.get("bakeoff", {})
    approaches = list(b.get("approaches") or APPROACH_IDS)
    wrapper_modes = list(b.get("wrapper_modes", [True, False]))
    seeds = list(b.get("seeds", [1, 2, 3]))
    trials = int(b.get("trials_per_config", 1))
    sim_seconds = float(b.get("sim_seconds", cfg.get("loop", {}).get("sim_seconds", 40.0)))
    report_path = Path(b.get("report_path", "runs/bakeoff_report.json"))
    report_path.parent.mkdir(parents=True, exist_ok=True)

    # Force sim for bakeoff unless explicitly live
    cfg = dict(cfg)
    cfg.setdefault("loop", {})
    cfg["loop"] = dict(cfg["loop"])
    cfg["loop"]["mode"] = cfg["loop"].get("mode", "sim")
    if cfg["loop"]["mode"] != "live":
        cfg["loop"]["mode"] = "sim"

    results: list[dict[str, Any]] = []
    for approach in approaches:
        for wrap in wrapper_modes:
            for i in range(trials):
                seed = seeds[i % len(seeds)]
                end = run_episode(
                    cfg,
                    approach_id=approach,
                    wrapper_enabled=bool(wrap),
                    seed=int(seed),
                    sim_seconds=sim_seconds,
                )
                critique = critique_run(end["trace_path"])
                row = {
                    "approach_id": approach,
                    "wrapper_enabled": bool(wrap),
                    "seed": int(seed),
                    "survive_s": end.get("survive_s"),
                    "hits": end.get("hits"),
                    "gems": end.get("gems"),
                    "breakout_count": end.get("breakout_count"),
                    "mean_entropy": end.get("mean_entropy"),
                    "alive": end.get("alive"),
                    "run_id": end.get("run_id"),
                    "trace_path": end.get("trace_path"),
                    "critique_notes": critique.get("notes", []),
                }
                results.append(row)
                print(
                    f"[bakeoff] {approach} wrap={wrap} seed={seed} "
                    f"survive={row['survive_s']:.2f}s hits={row['hits']} gems={row['gems']} "
                    f"entropy={row['mean_entropy']:.2f}"
                )

    summary = _summarize(results)
    report = {"results": results, "summary": summary}
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Wrote bakeoff report → {report_path}")
    return report


def _summarize(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    from collections import defaultdict

    groups: dict[tuple, list] = defaultdict(list)
    for r in results:
        key = (r["approach_id"], r["wrapper_enabled"])
        groups[key].append(r)
    out = []
    for (approach, wrap), rows in sorted(groups.items()):
        surv = [float(r["survive_s"]) for r in rows]
        ent = [float(r["mean_entropy"]) for r in rows]
        gems = [float(r["gems"]) for r in rows]
        out.append(
            {
                "approach_id": approach,
                "wrapper_enabled": wrap,
                "n": len(rows),
                "mean_survive_s": sum(surv) / len(surv),
                "mean_entropy": sum(ent) / len(ent),
                "mean_gems": sum(gems) / len(gems),
                "alive_rate": sum(1 for r in rows if r.get("alive")) / len(rows),
            }
        )
    out.sort(key=lambda x: x["mean_survive_s"], reverse=True)
    return out


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run mover bakeoff trials")
    parser.add_argument("--config", default="configs/bakeoff.yaml")
    args = parser.parse_args(argv)
    cfg = load_config(args.config)
    run_bakeoff(cfg)


if __name__ == "__main__":
    main()
