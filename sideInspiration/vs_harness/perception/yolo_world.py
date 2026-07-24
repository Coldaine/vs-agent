from __future__ import annotations

import time
from typing import Any

import numpy as np

from vs_harness.perception.base import PerceptionBackend
from vs_harness.perception.boxes import boxes_to_mask
from vs_harness.types import PerceptionFrame


class YoloWorldPerception(PerceptionBackend):
    """Open-vocab detector → dilated box union mask (optional ultralytics)."""

    name = "yolo_world"

    def __init__(
        self,
        enemy_prompts: list[str] | None = None,
        gem_prompts: list[str] | None = None,
        conf: float = 0.15,
        model_name: str = "yolov8s-world.pt",
    ):
        self.enemy_prompts = enemy_prompts or ["monster", "enemy", "bat", "skeleton"]
        self.gem_prompts = gem_prompts or ["gem", "crystal"]
        self.conf = conf
        self.model_name = model_name
        self._model = None
        self._init()

    def _init(self) -> None:
        try:
            from ultralytics import YOLO  # type: ignore
        except ImportError as exc:
            raise ImportError(
                "ultralytics not installed. `pip install ultralytics` or use perception.backend=mock"
            ) from exc
        self._model = YOLO(self.model_name)
        # Set classes / prompts when API supports it
        try:
            self._model.set_classes(self.enemy_prompts + self.gem_prompts)
        except Exception:
            pass

    def infer(self, frame_bgr: np.ndarray, timestamp_s: float) -> PerceptionFrame:
        assert self._model is not None
        t0 = time.perf_counter()
        h, w = frame_bgr.shape[:2]
        results = self._model.predict(frame_bgr, conf=self.conf, verbose=False)
        enemy_boxes: list[tuple[float, float, float, float]] = []
        gem_boxes: list[tuple[float, float, float, float]] = []
        enemy_scores: list[float] = []
        gem_scores: list[float] = []
        names = {}
        if results:
            r0 = results[0]
            names = getattr(r0, "names", {}) or {}
            if r0.boxes is not None and len(r0.boxes):
                xyxy = r0.boxes.xyxy.cpu().numpy()
                confs = r0.boxes.conf.cpu().numpy()
                clss = r0.boxes.cls.cpu().numpy().astype(int)
                for box, sc, cls_i in zip(xyxy, confs, clss):
                    label = str(names.get(int(cls_i), cls_i)).lower()
                    tup = (float(box[0]), float(box[1]), float(box[2]), float(box[3]))
                    if any(p.lower() in label or label in p.lower() for p in self.gem_prompts):
                        gem_boxes.append(tup)
                        gem_scores.append(float(sc))
                    else:
                        # default: treat as threat (open-vocab enemies)
                        enemy_boxes.append(tup)
                        enemy_scores.append(float(sc))

        threat = boxes_to_mask((h, w), enemy_boxes, enemy_scores, score_thresh=self.conf)
        gems = boxes_to_mask((h, w), gem_boxes, gem_scores, score_thresh=self.conf)
        player = np.zeros((h, w), dtype=bool)
        player[h // 2, w // 2] = True
        ms = (time.perf_counter() - t0) * 1000
        return PerceptionFrame(
            timestamp_s=timestamp_s,
            frame_bgr=frame_bgr,
            threat_union=threat,
            player_mask=player,
            gem_mask=gems,
            player_xy=(w / 2.0, h / 2.0),
            inference_ms=ms,
            backend=self.name,
            meta={"n_enemy_boxes": len(enemy_boxes), "n_gem_boxes": len(gem_boxes)},
        )


def try_build_yolo_world(cfg: dict[str, Any]) -> PerceptionBackend | None:
    perc = cfg.get("perception", {})
    try:
        return YoloWorldPerception(
            enemy_prompts=list(perc.get("enemy_prompts", [])),
            gem_prompts=list(perc.get("gem_prompts", [])),
            conf=float(perc.get("yolo_conf", 0.15)),
            model_name=str(perc.get("yolo_model", "yolov8s-world.pt")),
        )
    except Exception:
        return None
