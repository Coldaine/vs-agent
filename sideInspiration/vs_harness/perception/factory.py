from __future__ import annotations

from typing import Any

from vs_harness.perception.base import PerceptionBackend
from vs_harness.perception.mock import MockPerception
from vs_harness.perception.optical_flow import OpticalFlowPerception


def build_perception(cfg: dict[str, Any], sim=None) -> PerceptionBackend:
    perc = cfg.get("perception", {})
    backend = perc.get("backend", "mock")

    if backend in ("mock", "sim_gt"):
        return MockPerception(sim=sim)

    if backend == "color_heuristic":
        return MockPerception(sim=None)

    if backend == "optical_flow":
        return OpticalFlowPerception(
            mag_thresh=float(perc.get("flow_mag_thresh", 2.0)),
        )

    if backend == "sam3":
        from vs_harness.perception.sam3 import try_build_sam

        sam = try_build_sam(cfg)
        return sam if sam is not None else MockPerception(sim=sim)

    if backend == "yolo_world":
        from vs_harness.perception.yolo_world import try_build_yolo_world

        yolo = try_build_yolo_world(cfg)
        return yolo if yolo is not None else MockPerception(sim=sim)

    if backend == "fusion_yolo_flow":
        from vs_harness.perception.fusion import FusionPerception
        from vs_harness.perception.yolo_world import try_build_yolo_world

        primary = try_build_yolo_world(cfg) or MockPerception(sim=sim)
        prior = OpticalFlowPerception(mag_thresh=float(perc.get("flow_mag_thresh", 2.0)))
        return FusionPerception(primary, prior)

    if backend == "fusion_sam_flow":
        from vs_harness.perception.fusion import FusionPerception
        from vs_harness.perception.sam3 import try_build_sam

        primary = try_build_sam(cfg) or MockPerception(sim=sim)
        prior = OpticalFlowPerception(mag_thresh=float(perc.get("flow_mag_thresh", 2.0)))
        return FusionPerception(primary, prior)

    # Unknown → safe mock
    return MockPerception(sim=sim)


PERCEPTION_BACKENDS = (
    "mock",
    "color_heuristic",
    "optical_flow",
    "sam3",
    "yolo_world",
    "fusion_yolo_flow",
    "fusion_sam_flow",
)
