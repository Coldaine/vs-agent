from __future__ import annotations

import base64
import logging
import time
from typing import Any

import cv2
import httpx
import numpy as np

from vs_harness.perception.base import PerceptionBackend
from vs_harness.perception.masks import mask_centroid
from vs_harness.types import PerceptionFrame

logger = logging.getLogger(__name__)


def _decode_mask_png(b64: str, shape: tuple[int, int]) -> np.ndarray:
    png = base64.b64decode(b64)
    arr = np.frombuffer(png, dtype=np.uint8)
    mask = cv2.imdecode(arr, cv2.IMREAD_GRAYSCALE)
    if mask is None:
        raise RuntimeError("sam3 service returned undecodable mask png")
    if mask.shape != shape:
        mask = cv2.resize(mask, (shape[1], shape[0]), interpolation=cv2.INTER_NEAREST)
    return mask.astype(bool)


class Sam3HttpPerception(PerceptionBackend):
    """SAM 3 image PCS via the Docker sidecar (recommended).

    Talks to sideInspiration/sam3_service (default http://127.0.0.1:8090).
    Keeps torch/CUDA/HF gated weights out of the harness venv.
    """

    name = "sam3"

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:8090",
        enemy_prompts: list[str] | None = None,
        gem_prompts: list[str] | None = None,
        player_prompts: list[str] | None = None,
        downsample_max_side: int = 640,
        score_thresh: float = 0.5,
        timeout_s: float = 60.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.enemy_prompts = enemy_prompts or ["enemy", "monster"]
        self.gem_prompts = gem_prompts or []
        self.player_prompts = player_prompts or []
        self.downsample_max_side = downsample_max_side
        self.score_thresh = score_thresh
        self.timeout_s = timeout_s
        self._client = httpx.Client(timeout=timeout_s)

    def close(self) -> None:
        self._client.close()

    def _segment(self, frame_bgr: np.ndarray, prompts: list[str]) -> dict[str, Any]:
        ok, buf = cv2.imencode(".jpg", frame_bgr, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
        if not ok:
            raise RuntimeError("failed to jpeg-encode frame for sam3 service")
        payload = {
            "image_b64": base64.b64encode(buf.tobytes()).decode("ascii"),
            "prompts": prompts,
            "score_thresh": self.score_thresh,
            "downsample_max_side": self.downsample_max_side,
        }
        r = self._client.post(f"{self.base_url}/v1/segment", json=payload)
        r.raise_for_status()
        return r.json()

    def infer(self, frame_bgr: np.ndarray, timestamp_s: float) -> PerceptionFrame:
        t0 = time.perf_counter()
        oh, ow = frame_bgr.shape[:2]
        shape = (oh, ow)

        prompts = list(
            dict.fromkeys([*self.enemy_prompts, *self.gem_prompts, *self.player_prompts])
        )
        data = self._segment(frame_bgr, prompts)
        per = data.get("per_prompt_png_b64") or {}

        def or_prompts(keys: list[str]) -> np.ndarray:
            out = np.zeros(shape, dtype=bool)
            for p in keys:
                b64 = per.get(p)
                if b64:
                    out |= _decode_mask_png(b64, shape)
            return out

        threat = or_prompts(self.enemy_prompts)
        if not threat.any() and data.get("union_png_b64"):
            # Fallback if server is older and has no per_prompt map
            threat = _decode_mask_png(data["union_png_b64"], shape)

        gems = or_prompts(self.gem_prompts)
        player = or_prompts(self.player_prompts)
        pxy = mask_centroid(player, (ow / 2.0, oh / 2.0))
        if not player.any():
            player = np.zeros(shape, dtype=bool)
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
            meta={
                "transport": "http",
                "sam3_url": self.base_url,
                "checkpoint_hint": data.get("checkpoint_hint", "facebook/sam3"),
                "prompt_counts": data.get("prompt_counts", {}),
                "ids_discarded": True,
            },
        )


def try_build_sam(cfg: dict[str, Any]) -> PerceptionBackend | None:
    """Build Docker-backed SAM 3 client. Returns None if the sidecar is down."""
    perc = cfg.get("perception", {})
    base_url = str(perc.get("sam3_url", "http://127.0.0.1:8090")).rstrip("/")
    try:
        with httpx.Client(timeout=2.0) as c:
            r = c.get(f"{base_url}/health")
            r.raise_for_status()
            body = r.json()
            if body.get("ok") is False:
                return None
    except Exception as exc:  # noqa: BLE001
        logger.warning("sam3 sidecar unavailable at %s: %s", base_url, exc)
        return None

    return Sam3HttpPerception(
        base_url=base_url,
        enemy_prompts=list(perc.get("enemy_prompts", []) or ["enemy", "monster"]),
        gem_prompts=list(perc.get("gem_prompts", []) or []),
        player_prompts=list(perc.get("player_prompts", []) or []),
        downsample_max_side=int(perc.get("downsample_max_side", 640)),
        score_thresh=float(perc.get("sam_score_thresh", 0.5)),
        timeout_s=float(perc.get("sam3_timeout_s", 60.0)),
    )
