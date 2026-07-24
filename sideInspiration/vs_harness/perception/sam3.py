from __future__ import annotations

import time
from typing import Any

import cv2
import numpy as np

from vs_harness.perception.base import PerceptionBackend
from vs_harness.perception.masks import mask_centroid
from vs_harness.types import PerceptionFrame


class Sam3Perception(PerceptionBackend):
    """SAM 3 / 3.1 concept segmentation → union threat mask (no track IDs).

    Requires optional deps: torch + facebookresearch/sam3.
    Falls back is NOT automatic; build_perception chooses mock when unavailable.
    """

    name = "sam3"

    def __init__(
        self,
        version: str = "sam3.1",
        enemy_prompts: list[str] | None = None,
        gem_prompts: list[str] | None = None,
        player_prompts: list[str] | None = None,
        downsample_max_side: int = 640,
        device: str | None = None,
    ):
        self.version = version
        self.enemy_prompts = enemy_prompts or ["enemy", "monster"]
        self.gem_prompts = gem_prompts or ["gem"]
        self.player_prompts = player_prompts or ["player character"]
        self.downsample_max_side = downsample_max_side
        self.device = device
        self._processor = None
        self._model = None
        self._init_model()

    def _init_model(self) -> None:
        try:
            from sam3.model_builder import build_sam3_image_model
            from sam3.model.sam3_image_processor import Sam3Processor
        except ImportError as exc:
            raise ImportError(
                "sam3 package not installed. `pip install` facebookresearch/sam3 + torch, "
                "or set perception.backend=mock"
            ) from exc

        # Image model is preferred for per-frame union masks (no IDs kept).
        self._model = build_sam3_image_model()
        self._processor = Sam3Processor(self._model)

    def _resize(self, frame_bgr: np.ndarray) -> tuple[np.ndarray, float]:
        h, w = frame_bgr.shape[:2]
        scale = 1.0
        max_side = max(h, w)
        if max_side > self.downsample_max_side:
            scale = self.downsample_max_side / max_side
            frame_bgr = cv2.resize(
                frame_bgr,
                (int(w * scale), int(h * scale)),
                interpolation=cv2.INTER_AREA,
            )
        return frame_bgr, scale

    def _union_for_prompts(self, image_rgb: np.ndarray, prompts: list[str]) -> np.ndarray:
        assert self._processor is not None
        h, w = image_rgb.shape[:2]
        union = np.zeros((h, w), dtype=bool)
        # Prefer PIL if available
        try:
            from PIL import Image

            pil = Image.fromarray(image_rgb)
        except Exception:
            pil = image_rgb

        for prompt in prompts:
            try:
                state = self._processor.set_image(pil)
                output = self._processor.set_text_prompt(state=state, prompt=prompt)
                masks = output.get("masks")
                if masks is None:
                    continue
                # masks: NxHxW tensor/array
                arr = np.asarray(masks)
                if arr.ndim == 3:
                    union |= arr.astype(bool).any(axis=0)
                elif arr.ndim == 2:
                    union |= arr.astype(bool)
            except Exception:
                continue
        return union

    def infer(self, frame_bgr: np.ndarray, timestamp_s: float) -> PerceptionFrame:
        t0 = time.perf_counter()
        small, scale = self._resize(frame_bgr)
        rgb = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)
        threat = self._union_for_prompts(rgb, self.enemy_prompts)
        gems = self._union_for_prompts(rgb, self.gem_prompts)
        player = self._union_for_prompts(rgb, self.player_prompts)

        # Upscale masks to original size if needed
        oh, ow = frame_bgr.shape[:2]
        if threat.shape != (oh, ow):
            threat = cv2.resize(threat.astype(np.uint8), (ow, oh), interpolation=cv2.INTER_NEAREST).astype(bool)
            gems = cv2.resize(gems.astype(np.uint8), (ow, oh), interpolation=cv2.INTER_NEAREST).astype(bool)
            player = cv2.resize(player.astype(np.uint8), (ow, oh), interpolation=cv2.INTER_NEAREST).astype(bool)

        pxy = mask_centroid(player, (ow / 2.0, oh / 2.0))
        if not player.any():
            player = np.zeros((oh, ow), dtype=bool)
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
            meta={"sam_version": self.version, "scale": scale, "ids_discarded": True},
        )


def try_build_sam(cfg: dict[str, Any]) -> PerceptionBackend | None:
    perc = cfg.get("perception", {})
    try:
        return Sam3Perception(
            version=perc.get("sam_version", "sam3.1"),
            enemy_prompts=list(perc.get("enemy_prompts", [])),
            gem_prompts=list(perc.get("gem_prompts", [])),
            player_prompts=list(perc.get("player_prompts", [])),
            downsample_max_side=int(perc.get("downsample_max_side", 640)),
        )
    except Exception:
        return None
