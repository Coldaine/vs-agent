from __future__ import annotations

import time
from typing import Any

import numpy as np

from vs_harness.perception.base import PerceptionBackend
from vs_harness.types import PerceptionFrame


class FusionPerception(PerceptionBackend):
    """OR-fuse a primary backend with an optional fast prior (e.g. optical flow)."""

    name = "fusion"

    def __init__(self, primary: PerceptionBackend, prior: PerceptionBackend, prior_weight_or: bool = True):
        self.primary = primary
        self.prior = prior
        self.prior_weight_or = prior_weight_or
        self.name = f"fusion:{primary.name}+{prior.name}"

    def infer(self, frame_bgr: np.ndarray, timestamp_s: float) -> PerceptionFrame:
        t0 = time.perf_counter()
        a = self.primary.infer(frame_bgr, timestamp_s)
        b = self.prior.infer(frame_bgr, timestamp_s)
        threat = a.threat_union | b.threat_union if self.prior_weight_or else a.threat_union
        gems = a.gem_mask | b.gem_mask
        player = a.player_mask if a.player_mask.any() else b.player_mask
        ms = (time.perf_counter() - t0) * 1000
        return PerceptionFrame(
            timestamp_s=timestamp_s,
            frame_bgr=frame_bgr,
            threat_union=threat,
            player_mask=player,
            gem_mask=gems,
            player_xy=a.player_xy,
            inference_ms=ms,
            backend=self.name,
            meta={
                "primary_ms": a.inference_ms,
                "prior_ms": b.inference_ms,
                "primary": a.backend,
                "prior": b.backend,
            },
        )

    def close(self) -> None:
        self.primary.close()
        self.prior.close()
