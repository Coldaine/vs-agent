from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

import numpy as np


@dataclass
class CapturedFrame:
    timestamp_s: float
    frame_bgr: np.ndarray
    source: str


class FrameCapture(ABC):
    @abstractmethod
    def grab(self) -> CapturedFrame:
        raise NotImplementedError

    def close(self) -> None:
        return None
