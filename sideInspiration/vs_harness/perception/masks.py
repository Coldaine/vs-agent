from __future__ import annotations

import numpy as np
from scipy import ndimage


def dilate_bool(mask: np.ndarray, radius: int) -> np.ndarray:
    if radius <= 0:
        return mask.astype(bool)
    structure = np.ones((2 * radius + 1, 2 * radius + 1), dtype=bool)
    return ndimage.binary_dilation(mask.astype(bool), structure=structure)


def distance_to_threat(threat: np.ndarray) -> np.ndarray:
    """Distance transform: pixels farther from threat have larger values."""
    free = ~threat.astype(bool)
    return ndimage.distance_transform_edt(free).astype(np.float32)


def mask_centroid(mask: np.ndarray, fallback: tuple[float, float]) -> tuple[float, float]:
    ys, xs = np.where(mask)
    if len(xs) == 0:
        return fallback
    return float(xs.mean()), float(ys.mean())


def encode_rle(mask: np.ndarray) -> dict:
    """Simple row-major RLE for bool masks."""
    flat = mask.astype(np.uint8).ravel(order="C")
    if flat.size == 0:
        return {"size": [0, 0], "counts": []}
    counts: list[int] = []
    last = flat[0]
    run = 1
    # COCO-style often starts with zeros-run; we store value flips from first pixel
    counts.append(int(last))  # first value marker 0/1
    for val in flat[1:]:
        if val == last:
            run += 1
        else:
            counts.append(run)
            last = val
            run = 1
    counts.append(run)
    h, w = mask.shape
    return {"size": [int(h), int(w)], "counts": counts}


def decode_rle(rle: dict) -> np.ndarray:
    h, w = rle["size"]
    counts = rle["counts"]
    if not counts:
        return np.zeros((h, w), dtype=bool)
    first = counts[0]
    runs = counts[1:]
    flat = np.empty(h * w, dtype=np.uint8)
    idx = 0
    val = first
    for run in runs:
        flat[idx : idx + run] = val
        idx += run
        val = 1 - val
    return flat.reshape((h, w), order="C").astype(bool)
