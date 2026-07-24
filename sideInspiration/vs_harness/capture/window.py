from __future__ import annotations

import time
from typing import Any

import numpy as np

from vs_harness.capture.base import CapturedFrame, FrameCapture


class WindowCapture(FrameCapture):
    """Best-effort monitor capture via mss when installed."""

    def __init__(self, window_title: str, backend: str = "auto"):
        self.window_title = window_title
        self.backend = backend
        self._impl = self._build(backend)

    def _build(self, backend: str) -> Any:
        if backend in ("auto", "mss"):
            try:
                import mss  # type: ignore

                sct = mss.mss()
                mon = sct.monitors[1]
                return ("mss", sct, mon)
            except Exception:
                if backend == "mss":
                    raise
        raise RuntimeError(
            "No live capture backend available. Install `mss` or use loop.mode=sim / capture_backend=mock."
        )

    def grab(self) -> CapturedFrame:
        kind, sct, mon = self._impl
        assert kind == "mss"
        shot = sct.grab(mon)
        bgra = np.asarray(shot, dtype=np.uint8)
        bgr = bgra[:, :, :3].copy()
        return CapturedFrame(timestamp_s=time.perf_counter(), frame_bgr=bgr, source="mss")

    def close(self) -> None:
        kind, sct, _ = self._impl
        if kind == "mss":
            sct.close()


def build_capture(cfg: dict, sim=None) -> FrameCapture:
    from vs_harness.capture.mock import MockCapture
    from vs_harness.host.launch import focus_window

    host = cfg.get("host", {})
    loop = cfg.get("loop", {})
    backend = host.get("capture_backend", "auto")
    title = host.get("window_title", "Vampire Survivors")
    if loop.get("mode", "sim") == "sim" or backend == "mock":
        return MockCapture(sim=sim)
    # Best-effort focus before first grab
    focus_window(str(title))
    return WindowCapture(window_title=str(title), backend=backend)
