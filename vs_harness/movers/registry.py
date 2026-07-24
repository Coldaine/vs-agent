from __future__ import annotations

import os
from typing import Any

from vs_harness.movers.base import Mover
from vs_harness.movers.fast_vlm import FastVLMMover
from vs_harness.movers.free_space import FreeSpaceCorridorMover
from vs_harness.movers.potential_field import PotentialFieldMover
from vs_harness.movers.sector_density import SectorDensityMover

APPROACH_IDS = (
    "free_space_corridor",
    "sector_density",
    "potential_field",
    "fast_vlm",
)


def build_mover(cfg: dict[str, Any], approach_id: str | None = None) -> Mover:
    mover_cfg = cfg.get("mover", {})
    perc = cfg.get("perception", {})
    approach = approach_id or mover_cfg.get("approach_id", "free_space_corridor")
    dilate = int(perc.get("contact_dilate_px", 8))
    gem_w = float(mover_cfg.get("gem_weight", 0.35))
    orbit = float(mover_cfg.get("orbit_bias", 0.15))
    sectors = int(mover_cfg.get("sector_count", 16))

    if approach == "free_space_corridor":
        return FreeSpaceCorridorMover(contact_dilate_px=dilate, gem_weight=gem_w, orbit_bias=orbit)
    if approach == "sector_density":
        return SectorDensityMover(sector_count=sectors, contact_dilate_px=dilate, gem_weight=gem_w)
    if approach == "potential_field":
        return PotentialFieldMover(contact_dilate_px=dilate, gem_weight=gem_w)
    if approach == "fast_vlm":
        openai = cfg.get("openai", {})
        key_env = openai.get("api_key_env", "VS_OPENAI_API_KEY")
        return FastVLMMover(
            base_url=str(openai.get("base_url", "https://api.openai.com/v1")),
            api_key=os.environ.get(key_env),
            model=str(openai.get("follower_model", "gpt-4o-mini")),
            timeout_s=float(openai.get("timeout_s", 30.0)),
        )
    raise ValueError(f"Unknown approach_id: {approach}")
