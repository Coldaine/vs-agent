from __future__ import annotations

import time

import cv2
import numpy as np

from vs_harness.perception.base import PerceptionBackend
from vs_harness.types import PerceptionFrame


class MockPerception(PerceptionBackend):
    """Color-heuristic / ground-truth perception for sim frames.

    Sim enemies are reddish, gems magenta, player green — see SwarmSim.render.
    Optionally bind a SwarmSim for perfect masks.
    """

    name = "mock"

    def __init__(self, sim=None):
        self.sim = sim

    def infer(self, frame_bgr: np.ndarray, timestamp_s: float) -> PerceptionFrame:
        t0 = time.perf_counter()
        if self.sim is not None:
            threat, player, gems, pxy = self.sim.ground_truth_masks()
            ms = (time.perf_counter() - t0) * 1000
            return PerceptionFrame(
                timestamp_s=timestamp_s,
                frame_bgr=frame_bgr,
                threat_union=threat,
                player_mask=player,
                gem_mask=gems,
                player_xy=pxy,
                inference_ms=ms,
                backend=self.name,
                meta={"source": "sim_gt"},
            )

        # HSV thresholds for live-ish mock without sim binding
        hsv = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2HSV)
        threat = cv2.inRange(hsv, (0, 80, 80), (15, 255, 255)) > 0
        threat |= cv2.inRange(hsv, (160, 80, 80), (180, 255, 255)) > 0
        gems = cv2.inRange(hsv, (130, 60, 80), (170, 255, 255)) > 0
        player = cv2.inRange(hsv, (35, 60, 60), (95, 255, 255)) > 0
        h, w = frame_bgr.shape[:2]
        if player.any():
            ys, xs = np.where(player)
            pxy = (float(xs.mean()), float(ys.mean()))
        else:
            pxy = (w / 2.0, h / 2.0)
            player = np.zeros((h, w), dtype=bool)
            player[int(pxy[1]), int(pxy[0])] = True
        ms = (time.perf_counter() - t0) * 1000
        return PerceptionFrame(
            timestamp_s=timestamp_s,
            frame_bgr=frame_bgr,
            threat_union=threat,
            player_mask=player,
            gem_mask=gems,
            player_xy=pxy,
            inference_ms=ms,
            backend=self.name,
            meta={"source": "color_heuristic"},
        )
