from __future__ import annotations

import numpy as np

from vs_harness.types import ScreenMode


class ModeDetector:
    """Cheap screen-mode classifier.

    Live game: template/OCR hooks can be added. For sim/mock frames we always
    report PLAYING unless an external override is set.
    """

    def __init__(self) -> None:
        self.override: ScreenMode | None = None

    def detect(self, frame_bgr: np.ndarray) -> ScreenMode:
        if self.override is not None:
            return self.override

        # Heuristic placeholders for live UI chrome (dark overlay + bright panel)
        h, w = frame_bgr.shape[:2]
        if h < 8 or w < 8:
            return ScreenMode.UNKNOWN

        center = frame_bgr[h // 3 : 2 * h // 3, w // 4 : 3 * w // 4]
        mean = float(center.mean())
        # Very bright centered panel on dark frame → likely level-up
        border = np.concatenate(
            [
                frame_bgr[: h // 10].reshape(-1, 3),
                frame_bgr[-h // 10 :].reshape(-1, 3),
            ],
            axis=0,
        )
        border_mean = float(border.mean())
        if mean > 140 and border_mean < 50:
            return ScreenMode.LEVELUP

        # Mostly black → title / dead
        if float(frame_bgr.mean()) < 12:
            return ScreenMode.TITLE

        return ScreenMode.PLAYING
