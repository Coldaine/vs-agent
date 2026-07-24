from __future__ import annotations

import time

import numpy as np

from vs_harness.capture.base import CapturedFrame, FrameCapture
from vs_harness.sim.swarm_sim import SwarmSim


class MockCapture(FrameCapture):
    """Pulls frames from the swarm simulator (or a static blank)."""

    def __init__(self, sim: SwarmSim | None = None, width: int = 320, height: int = 240):
        self.sim = sim
        self.width = width
        self.height = height

    def grab(self) -> CapturedFrame:
        ts = time.perf_counter()
        if self.sim is not None:
            frame = self.sim.render()
        else:
            frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        return CapturedFrame(timestamp_s=ts, frame_bgr=frame, source="mock")
