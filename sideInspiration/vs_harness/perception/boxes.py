from __future__ import annotations

import numpy as np


def boxes_to_mask(
    shape_hw: tuple[int, int],
    boxes_xyxy: list[tuple[float, float, float, float]] | np.ndarray,
    scores: list[float] | np.ndarray | None = None,
    score_thresh: float = 0.2,
) -> np.ndarray:
    """Rasterize axis-aligned boxes into a boolean union mask."""
    h, w = shape_hw
    mask = np.zeros((h, w), dtype=bool)
    if boxes_xyxy is None:
        return mask
    boxes = np.asarray(boxes_xyxy, dtype=np.float32)
    if boxes.size == 0:
        return mask
    if boxes.ndim == 1:
        boxes = boxes.reshape(1, 4)
    if scores is None:
        scores_arr = np.ones(len(boxes), dtype=np.float32)
    else:
        scores_arr = np.asarray(scores, dtype=np.float32)
    for (x1, y1, x2, y2), sc in zip(boxes, scores_arr):
        if sc < score_thresh:
            continue
        xa, xb = int(max(0, np.floor(x1))), int(min(w, np.ceil(x2)))
        ya, yb = int(max(0, np.floor(y1))), int(min(h, np.ceil(y2)))
        if xb > xa and yb > ya:
            mask[ya:yb, xa:xb] = True
    return mask
