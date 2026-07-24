from __future__ import annotations

import time

import cv2
import numpy as np

from vs_harness.perception.base import PerceptionBackend
from vs_harness.types import PerceptionFrame


class OpticalFlowPerception(PerceptionBackend):
    """Motion-magnitude threat prior via Farneback optical flow.

    Not sufficient alone for Vampire Survivors (FX/gems move too), but useful as a
    fast filler between SAM/YOLO ticks or fused later.
    """

    name = "optical_flow"

    def __init__(self, mag_thresh: float = 2.0, blur_ksize: int = 5):
        self.mag_thresh = mag_thresh
        self.blur_ksize = blur_ksize
        self._prev_gray: np.ndarray | None = None

    def infer(self, frame_bgr: np.ndarray, timestamp_s: float) -> PerceptionFrame:
        t0 = time.perf_counter()
        h, w = frame_bgr.shape[:2]
        gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
        threat = np.zeros((h, w), dtype=bool)
        if self._prev_gray is not None and self._prev_gray.shape == gray.shape:
            flow = cv2.calcOpticalFlowFarneback(
                self._prev_gray,
                gray,
                None,
                0.5,
                3,
                15,
                3,
                5,
                1.2,
                0,
            )
            mag, _ = cv2.cartToPolar(flow[..., 0], flow[..., 1])
            if self.blur_ksize > 1:
                mag = cv2.GaussianBlur(mag, (self.blur_ksize, self.blur_ksize), 0)
            threat = mag > self.mag_thresh
            # Ignore near-static center blob somewhat (player often low relative motion)
            cy, cx = h // 2, w // 2
            threat[cy - 4 : cy + 5, cx - 4 : cx + 5] = False
        self._prev_gray = gray

        player = np.zeros((h, w), dtype=bool)
        player[h // 2, w // 2] = True
        gems = np.zeros((h, w), dtype=bool)
        ms = (time.perf_counter() - t0) * 1000
        return PerceptionFrame(
            timestamp_s=timestamp_s,
            frame_bgr=frame_bgr,
            threat_union=threat,
            player_mask=player,
            gem_mask=gems,
            player_xy=(w / 2.0, h / 2.0),
            inference_ms=ms,
            backend=self.name,
            meta={"mag_thresh": self.mag_thresh},
        )
