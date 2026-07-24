import json

from trace import EpisodeWriter, hash_prompt


def test_hash_prompt_is_stable_hex(tmp_path):
    p = tmp_path / "prompt.md"
    p.write_text("hello pilot")
    h1 = hash_prompt(str(p))
    h2 = hash_prompt(str(p))
    assert h1 == h2
    assert len(h1) == 12
    assert all(c in "0123456789abcdef" for c in h1)


def test_episode_writer_outputs(tmp_path):
    ep = EpisodeWriter(str(tmp_path), "run_test")
    ep.log_tick(hp=100, level=1, timer="00:10", inventory=[],
                threats=[0] * 8, gems=[0] * 8, rule_fired="clean",
                latency_ms=120, action="E", reflex_override=False)
    ep.log_planner(["Whip", "Garlic"], "Whip", "range", "farm gems")
    ep.close(survived_s=10.0, level=1, kills=3, invalid=False,
             prompt_hashes={"pilot": "abc", "planner": "def"})

    run_dir = tmp_path / "run_test"
    assert (run_dir / "states.jsonl").exists()
    assert (run_dir / "planner.jsonl").exists()

    outcome = json.loads((run_dir / "outcome.json").read_text())
    assert outcome["survived_s"] == 10.0
    assert outcome["kills"] == 3

    planner = json.loads((run_dir / "planner.jsonl").read_text().strip())
    assert planner["pick"] == "Whip"
