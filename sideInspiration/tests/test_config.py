from vs_harness.config import load_config


def test_load_default():
    cfg = load_config("configs/default.yaml")
    assert cfg["host"]["window_title"] == "Vampire Survivors"
    assert "leader_model" in cfg["openai"]


def test_bakeoff_inherits():
    cfg = load_config("configs/bakeoff.yaml")
    assert "bakeoff" in cfg
    assert cfg["host"]["prefer_windowed"] is True
    assert "free_space_corridor" in cfg["bakeoff"]["approaches"]
