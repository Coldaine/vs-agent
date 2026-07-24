"""Minimal GPU HTTP service for SAM 3 image concept segmentation.

Exposes per-frame text→mask PCS. This is the API that fits Vampire Survivors
threat-union perception (discard instance IDs every frame).

Note on versions:
  - Image PCS uses build_sam3_image_model(), which loads facebook/sam3 (sam3.pt).
  - Meta's SAM 3.1 multiplex checkpoints are for the *video* predictor path.
  - We still pin the latest facebookresearch/sam3 package in the image; call this
    service "sam3" for honesty. Env SAM3_VERSION is reserved for future wiring.
"""

from __future__ import annotations

import base64
import logging
import os
import threading
import time
from typing import Any

import cv2
import numpy as np
from fastapi import FastAPI, HTTPException
from PIL import Image
from pydantic import BaseModel, Field

logger = logging.getLogger("sam3_service")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

app = FastAPI(title="sam3-image-pcs", version="0.1.0")

_lock = threading.Lock()
_processor = None
_model = None
_load_error: str | None = None


class SegmentRequest(BaseModel):
    image_b64: str = Field(..., description="JPEG/PNG bytes, base64-encoded")
    prompts: list[str] = Field(..., min_length=1)
    score_thresh: float = 0.5
    downsample_max_side: int = 640


class SegmentResponse(BaseModel):
    width: int
    height: int
    union_png_b64: str
    per_prompt_png_b64: dict[str, str]
    prompt_counts: dict[str, int]
    inference_ms: float
    backend: str = "sam3_image"
    checkpoint_hint: str = "facebook/sam3"


def _decode_image(image_b64: str) -> np.ndarray:
    raw = base64.b64decode(image_b64)
    arr = np.frombuffer(raw, dtype=np.uint8)
    bgr = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if bgr is None:
        raise HTTPException(status_code=400, detail="Could not decode image_b64")
    return bgr


def _encode_mask_png(mask: np.ndarray) -> str:
    u8 = (mask.astype(np.uint8) * 255)
    ok, buf = cv2.imencode(".png", u8)
    if not ok:
        raise HTTPException(status_code=500, detail="mask encode failed")
    return base64.b64encode(buf.tobytes()).decode("ascii")


def _resize(frame_bgr: np.ndarray, max_side: int) -> tuple[np.ndarray, float]:
    h, w = frame_bgr.shape[:2]
    scale = 1.0
    m = max(h, w)
    if m > max_side:
        scale = max_side / m
        frame_bgr = cv2.resize(
            frame_bgr,
            (int(w * scale), int(h * scale)),
            interpolation=cv2.INTER_AREA,
        )
    return frame_bgr, scale


def _ensure_model() -> Any:
    global _processor, _model, _load_error
    if _processor is not None:
        return _processor

    with _lock:
        if _processor is not None:
            return _processor
        # Allow retry after image rebuild / deps fix (do not sticky-fail forever)
        _load_error = None
        try:
            import torch
            from sam3.model_builder import build_sam3_image_model
            from sam3.model.sam3_image_processor import Sam3Processor

            device = "cuda" if torch.cuda.is_available() else "cpu"
            logger.info("Loading SAM 3 image model on %s (HF_HOME=%s)", device, os.environ.get("HF_HOME"))
            # Image builder hardcodes facebook/sam3 checkpoint download when load_from_HF=True.
            # SAM3 fused kernels cast activations to bf16; keep weights in bf16 too (5090).
            _model = build_sam3_image_model(device=device, load_from_HF=True)
            if device == "cuda":
                _model = _model.to(device=device, dtype=torch.bfloat16)
            _model.eval()
            _processor = Sam3Processor(_model, confidence_threshold=0.5)
            logger.info("SAM 3 image model ready (dtype=%s)", next(_model.parameters()).dtype)
            return _processor
        except Exception as exc:  # noqa: BLE001
            _load_error = (
                f"Failed to load SAM 3: {exc}. "
                "Ensure HF_TOKEN is set and you accepted facebook/sam3 on Hugging Face."
            )
            logger.exception("model load failed")
            raise HTTPException(status_code=503, detail=_load_error) from exc


def _segment_prompts(
    processor: Any, pil: Image.Image, prompts: list[str], score_thresh: float
) -> tuple[np.ndarray, dict[str, np.ndarray], dict[str, int]]:
    import torch

    # Model weights are bf16 on CUDA; autocast casts float image tensors to match.
    amp_ctx = (
        torch.autocast(device_type="cuda", dtype=torch.bfloat16)
        if torch.cuda.is_available()
        else torch.autocast(device_type="cpu", enabled=False)
    )
    with torch.inference_mode(), amp_ctx:
        # set_image once per frame, then prompt — avoids re-encoding the vision tower per string
        state = processor.set_image(pil)
        if hasattr(processor, "confidence_threshold"):
            processor.confidence_threshold = score_thresh

        w, h = pil.size
        union = np.zeros((h, w), dtype=bool)
        per_prompt: dict[str, np.ndarray] = {}
        counts: dict[str, int] = {}
        for prompt in prompts:
            mask = np.zeros((h, w), dtype=bool)
            try:
                output = processor.set_text_prompt(state=state, prompt=prompt)
                masks = output.get("masks")
                if masks is None:
                    counts[prompt] = 0
                else:
                    arr = masks
                    if hasattr(arr, "detach"):
                        arr = arr.detach().float().cpu().numpy()
                    else:
                        arr = np.asarray(arr)
                    if arr.ndim == 4:
                        arr = arr[:, 0]
                    if arr.ndim == 3:
                        counts[prompt] = int(arr.shape[0])
                        mask = arr.astype(bool).any(axis=0)
                    elif arr.ndim == 2:
                        counts[prompt] = 1
                        mask = arr.astype(bool)
                    else:
                        counts[prompt] = 0
            except Exception as exc:  # noqa: BLE001
                logger.warning("prompt %r failed: %s", prompt, exc)
                counts[prompt] = 0
            per_prompt[prompt] = mask
            union |= mask
        return union, per_prompt, counts


@app.get("/health")
def health() -> dict[str, Any]:
    import torch

    return {
        "ok": True,
        "cuda": bool(torch.cuda.is_available()),
        "device_count": int(torch.cuda.device_count()) if torch.cuda.is_available() else 0,
        "model_loaded": _processor is not None,
        "load_error": _load_error,
        "hf_token_set": bool(os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN")),
    }


@app.post("/v1/segment", response_model=SegmentResponse)
def segment(req: SegmentRequest) -> SegmentResponse:
    t0 = time.perf_counter()
    processor = _ensure_model()
    bgr = _decode_image(req.image_b64)
    oh, ow = bgr.shape[:2]
    small, _scale = _resize(bgr, req.downsample_max_side)
    rgb = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)
    pil = Image.fromarray(rgb)

    union_small, per_small, counts = _segment_prompts(
        processor, pil, req.prompts, req.score_thresh
    )

    def up(m: np.ndarray) -> np.ndarray:
        if m.shape == (oh, ow):
            return m
        return cv2.resize(m.astype(np.uint8), (ow, oh), interpolation=cv2.INTER_NEAREST).astype(bool)

    union = up(union_small)
    per_png = {p: _encode_mask_png(up(m)) for p, m in per_small.items()}

    ms = (time.perf_counter() - t0) * 1000
    return SegmentResponse(
        width=ow,
        height=oh,
        union_png_b64=_encode_mask_png(union),
        per_prompt_png_b64=per_png,
        prompt_counts=counts,
        inference_ms=ms,
    )


@app.post("/v1/warmup")
def warmup() -> dict[str, Any]:
    _ensure_model()
    return {"ok": True, "model_loaded": True}
