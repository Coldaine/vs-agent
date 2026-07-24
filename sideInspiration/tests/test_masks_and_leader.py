import numpy as np

from vs_harness.planner.strategy import StrategyPlanner
from vs_harness.perception.masks import decode_rle, encode_rle
from vs_harness.types import ScreenMode


def test_rle_roundtrip():
    mask = np.zeros((20, 30), dtype=bool)
    mask[5:10, 3:8] = True
    out = decode_rle(encode_rle(mask))
    assert out.shape == mask.shape
    assert np.array_equal(out, mask)


def test_leader_levelup_ranking(monkeypatch):
    monkeypatch.delenv("NOPE", raising=False)
    cfg = {
        "planner": {"enabled": True, "knowledge_pack": "configs/evolution_knowledge.yaml", "intent_refresh_s": 1},
        "openai": {"base_url": "http://x", "api_key_env": "NOPE", "leader_model": "x"},
    }
    planner = StrategyPlanner(cfg)
    idx = planner.choose_levelup_option(["Empty Tome", "Garlic", "Stone"])
    assert idx == 0  # Empty Tome enables Magic Wand evolution
    intent = planner.maybe_refresh(ScreenMode.PLAYING, None, now_s=10.0)
    assert intent.mode in {"farm", "kite", "boss", "gem_vacuum", "chest_hunt"}

