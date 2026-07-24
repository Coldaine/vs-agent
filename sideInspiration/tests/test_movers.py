from vs_harness.movers.registry import APPROACH_IDS, build_mover
from vs_harness.sim.swarm_sim import SwarmSim
from vs_harness.types import IntentPacket


def _cfg(approach: str) -> dict:
    return {
        "mover": {"approach_id": approach, "gem_weight": 0.3, "sector_count": 12},
        "perception": {"contact_dilate_px": 6},
        "openai": {"base_url": "http://localhost", "follower_model": "x", "api_key_env": "NOPE"},
    }


def test_all_movers_propose(monkeypatch):
    monkeypatch.delenv("NOPE", raising=False)
    sim = SwarmSim(seed=1, n_enemies=25)
    threat, player, gems, pxy = sim.ground_truth_masks()
    from vs_harness.types import PerceptionFrame

    perc = PerceptionFrame(
        timestamp_s=0.0,
        frame_bgr=sim.render(),
        threat_union=threat,
        player_mask=player,
        gem_mask=gems,
        player_xy=pxy,
        inference_ms=0.1,
        backend="mock",
    )
    intent = IntentPacket(mode="kite", attractors=["open_space"], orbit="cw")
    for approach in APPROACH_IDS:
        mover = build_mover(_cfg(approach), approach_id=approach)
        prop = mover.propose(perc, intent)
        assert prop.heading in {"N", "NE", "E", "SE", "S", "SW", "W", "NW", "HOLD"}
        assert prop.clearance_px >= 0
