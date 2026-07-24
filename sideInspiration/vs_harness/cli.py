from __future__ import annotations

import argparse
import json

from vs_harness.config import load_config
from vs_harness.loop.harness import run_episode
from vs_harness.trace.critique import critique_path_to_json


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Vampire Survivors agent harness")
    sub = parser.add_subparsers(dest="cmd", required=True)

    run_p = sub.add_parser("run", help="Run one episode (sim or live)")
    run_p.add_argument("--config", default="configs/default.yaml")
    run_p.add_argument("--approach", default=None)
    run_p.add_argument("--wrapper", choices=["on", "off", "config"], default="config")
    run_p.add_argument("--seed", type=int, default=None)
    run_p.add_argument("--seconds", type=float, default=None)

    crit_p = sub.add_parser("critique", help="Critique a trace JSONL")
    crit_p.add_argument("trace")
    crit_p.add_argument("--out", default=None)

    host_p = sub.add_parser("host-check", help="Validate host/endpoint config")
    host_p.add_argument("--config", default="configs/default.yaml")

    sub.add_parser("vision-review", help="Print VLM / vision candidate review")

    args = parser.parse_args(argv)

    if args.cmd == "host-check":
        from vs_harness.host_check import run_check

        raise SystemExit(run_check(args.config))

    if args.cmd == "vision-review":
        from vs_harness.vision_candidates import print_review

        print_review()
        return

    if args.cmd == "critique":
        report = critique_path_to_json(args.trace, out=args.out)
        print(json.dumps(report, indent=2))
        return

    if args.cmd == "run":
        cfg = load_config(args.config)
        wrap = None
        if args.wrapper == "on":
            wrap = True
        elif args.wrapper == "off":
            wrap = False
        if args.seconds is not None:
            cfg.setdefault("loop", {})["sim_seconds"] = args.seconds
        end = run_episode(
            cfg,
            approach_id=args.approach,
            wrapper_enabled=wrap,
            seed=args.seed,
        )
        print(json.dumps(end, indent=2))
        return


if __name__ == "__main__":
    main()
