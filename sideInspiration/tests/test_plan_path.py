from vs_harness.config import load_config
from vs_harness.host.launch import LaunchResult, env_endpoint_summary, launch_or_attach
from vs_harness.planner.menu import extract_levelup_options, handle_paused_ui
from vs_harness.planner.strategy import StrategyPlanner
from vs_harness.loop.harness import run_episode
from vs_harness.trace.writer import read_trace
from vs_harness.types import ScreenMode
from vs_harness.control.input_injector import InputInjector


def test_vlm_follower_config_loads():
    cfg = load_config("configs/vlm_follower.yaml")
    assert cfg["loop"]["control_style"] == "vlm_follower"
    assert cfg["loop"]["follower_hz"] == 2.0
    assert cfg["mover"]["approach_id"] == "fast_vlm"


def test_vlm_follower_sim_episode(tmp_path):
    cfg = load_config("configs/vlm_follower.yaml")
    cfg["loop"]["sim_seconds"] = 2.0
    cfg["host"]["target_fps"] = 60
    cfg["trace"]["root"] = str(tmp_path)
    cfg["trace"]["save_masks_rle"] = False
    end = run_episode(cfg, seed=1)
    assert end["approach_id"] == "fast_vlm"
    events = read_trace(end["trace_path"])
    assert any(e.get("type") == "run_start" and e.get("control_style") == "vlm_follower" for e in events)
    # Sticky ticks should appear between 2 Hz pilot evaluations
    assert any(e.get("sticky") for e in events if e.get("type") == "tick")


def test_launch_attach_manual_when_no_window():
    cfg = {
        "host": {
            "window_title": "DefinitelyNotARealWindowXYZ",
            "steam_app_id": None,
            "launch_command": None,
        }
    }
    result = launch_or_attach(cfg)
    assert isinstance(result, LaunchResult)
    assert result.method == "manual"
    assert result.ok is False


def test_endpoint_summary():
    cfg = load_config("configs/default.yaml")
    summary = env_endpoint_summary(cfg)
    assert "base_url" in summary
    assert "leader_model" in summary


def test_paused_menu_handler():
    cfg = load_config("configs/default.yaml")
    planner = StrategyPlanner(cfg)
    injector = InputInjector(live=False)
    decision = handle_paused_ui(ScreenMode.LEVELUP, None, planner, injector, now_s=1.0)
    assert "choice_index" in decision
    assert len(decision["options"]) >= 1
    assert extract_levelup_options(None)

