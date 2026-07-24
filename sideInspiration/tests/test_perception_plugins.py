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


def test_sam3_http_client_parses_masks(monkeypatch):
    """Unit-test the HTTP client without a live GPU container."""
    import base64

    import cv2

    from vs_harness.perception.sam3 import Sam3HttpPerception

    frame = np.zeros((40, 60, 3), dtype=np.uint8)
    threat = np.zeros((40, 60), dtype=np.uint8)
    threat[10:20, 15:25] = 255
    ok, buf = cv2.imencode(".png", threat)
    assert ok
    png_b64 = base64.b64encode(buf.tobytes()).decode("ascii")

    class _Resp:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "width": 60,
                "height": 40,
                "union_png_b64": png_b64,
                "per_prompt_png_b64": {"enemy": png_b64, "monster": png_b64},
                "prompt_counts": {"enemy": 1, "monster": 1},
                "checkpoint_hint": "facebook/sam3",
                "inference_ms": 1.0,
            }

    class _Client:
        def post(self, url, json=None):  # noqa: A002
            assert url.endswith("/v1/segment")
            assert "enemy" in json["prompts"]
            return _Resp()

        def close(self):
            return None

    perc = Sam3HttpPerception(
        base_url="http://test",
        enemy_prompts=["enemy", "monster"],
        gem_prompts=[],
        player_prompts=[],
    )
    monkeypatch.setattr(perc, "_client", _Client())
    out = perc.infer(frame, 0.0)
    assert out.threat_union[12, 18]
    assert out.meta["transport"] == "http"
    assert out.backend == "sam3"
