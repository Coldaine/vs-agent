from vs_harness.config import load_config
from vs_harness.loop.harness import run_episode
from vs_harness.trace.critique import critique_run
from vs_harness.trace.writer import read_trace


def test_sim_episode_and_critique(tmp_path):
    cfg = load_config("configs/default.yaml")
    cfg["loop"]["mode"] = "sim"
    cfg["loop"]["sim_seconds"] = 2.0
    cfg["host"]["target_fps"] = 60
    cfg["trace"]["root"] = str(tmp_path)
    cfg["trace"]["save_masks_rle"] = False
    cfg["mover"]["approach_id"] = "sector_density"
    end = run_episode(cfg, seed=3)
    assert end["survive_s"] > 0
    events = read_trace(end["trace_path"])
    types = {e["type"] for e in events}
    assert "run_start" in types and "run_end" in types and "tick" in types
    report = critique_run(end["trace_path"])
    assert report["approach_id"] == "sector_density"
