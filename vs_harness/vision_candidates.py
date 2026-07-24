from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import yaml

from vs_harness.config import load_config


def load_candidates(path: str | Path = "configs/vision_candidates.yaml") -> dict[str, Any]:
    path = Path(path)
    if not path.exists():
        path = Path.cwd() / path
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def summarize(role: str | None = None) -> list[dict[str, Any]]:
    data = load_candidates()
    rows = data.get("candidates", [])
    if role:
        rows = [r for r in rows if r.get("role") == role]
    rows = sorted(rows, key=lambda r: (r.get("priority", 99), r.get("id", "")))
    return rows


def print_review() -> None:
    data = load_candidates()
    print("=== VS harness vision / VLM candidate review ===\n")
    for role in ("perception", "fast_mover", "slow_leader"):
        print(f"## {role}")
        for c in summarize(role):
            print(f"- {c['id']} [{c.get('latency_tier')}] — {c.get('notes', '').strip()[:160]}...")
        print()
    print("Recommended perception bakeoff order:")
    for x in data.get("recommended_bakeoff_order", {}).get("perception", []):
        print(f"  • {x}")
    print("\nDesign guidance:")
    for g in data.get("design_guidance", []):
        print(f"  • {g}")


def apply_follower_hint(cfg_path: str, candidate_id: str) -> dict[str, Any]:
    """Return config with openai.follower_model set from a fast_mover candidate hint."""
    cfg = load_config(cfg_path)
    for c in summarize("fast_mover"):
        if c.get("id") == candidate_id and c.get("openai_model_hint"):
            cfg.setdefault("openai", {})["follower_model"] = c["openai_model_hint"]
            break
    return cfg


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Review vision/VLM candidates")
    parser.add_argument("--role", default=None, choices=["perception", "fast_mover", "slow_leader"])
    args = parser.parse_args(argv)
    if args.role:
        for c in summarize(args.role):
            print(f"{c['id']}\t{c.get('latency_tier')}\t{c.get('harness_backend') or c.get('harness_mover')}")
    else:
        print_review()


if __name__ == "__main__":
    main()
