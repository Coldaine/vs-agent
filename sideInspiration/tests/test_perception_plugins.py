import numpy as np

from vs_harness.perception.boxes import boxes_to_mask
from vs_harness.perception.factory import PERCEPTION_BACKENDS, build_perception
from vs_harness.sim.swarm_sim import SwarmSim
from vs_harness.vision_candidates import load_candidates, summarize


def test_boxes_to_mask():
    mask = boxes_to_mask((40, 50), [(10, 10, 20, 25)], scores=[0.9], score_thresh=0.2)
    assert mask[12, 15]
    assert not mask[0, 0]


def test_optical_flow_runs():
    sim = SwarmSim(seed=0)
    perc = build_perception({"perception": {"backend": "optical_flow"}}, sim=sim)
    a = perc.infer(sim.render(), 0.0)
    sim.step("E")
    b = perc.infer(sim.render(), 0.1)
    assert a.threat_union.shape == b.threat_union.shape
    assert perc.name == "optical_flow"


def test_factory_known_backends():
    sim = SwarmSim(seed=1)
    for backend in ("mock", "color_heuristic", "optical_flow"):
        p = build_perception({"perception": {"backend": backend}}, sim=sim)
        out = p.infer(sim.render(), 0.0)
        assert out.threat_union.ndim == 2
    assert "yolo_world" in PERCEPTION_BACKENDS
    assert "sam3" in PERCEPTION_BACKENDS


def test_vision_candidates_registry():
    data = load_candidates()
    assert data.get("candidates")
    perc = summarize("perception")
    assert any(c["id"] == "sam3_1" for c in perc)
    assert any(c["id"] == "yolo_world" for c in perc)
    movers = summarize("fast_mover")
    assert any("smolvlm" in c["id"] for c in movers)
