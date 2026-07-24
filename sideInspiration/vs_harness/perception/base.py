from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np

from vs_harness.types import PerceptionFrame


class PerceptionBackend(ABC):
    name: str = "base"

    @abstractmethod
    def infer(self, frame_bgr: np.ndarray, timestamp_s: float) -> PerceptionFrame:
        raise NotImplementedError
