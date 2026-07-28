"""Safety and boundary tests for the LangGraph-to-spine game tools."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "spine"))

import game_tools  # noqa: E402


class FakeFrame:
    width = 100
    height = 100
    image = object()


class FakeIO:
    def __init__(self) -> None:
        self.neutralized = 0
        self.closed = 0

    def screenshot(self) -> FakeFrame:
        return FakeFrame()

    def neutralize(self) -> None:
        self.neutralized += 1

    def close(self) -> None:
        self.closed += 1


class FakeController:
    def __init__(self, *, reject: bool = False, fail_tick: bool = False) -> None:
        self.reject = reject
        self.fail_tick = fail_tick
        self.submissions: list[tuple[str, float]] = []
        self.ticks = 0
        self.neutralized = 0

    def submit_follower_proposal(self, direction: str, latency_ms: float) -> bool:
        self.submissions.append((direction, latency_ms))
        return not self.reject

    def tick(self, detections, player, screen_type):
        if self.fail_tick:
            raise RuntimeError("tick failed")
        self.ticks += 1
        return type("Tick", (), {
            "follower_latency_ms": 42.0,
            "rule_fired": "clean",
            "action": "NE",
        })()

    def neutralize(self) -> None:
        self.neutralized += 1


class FakePerception:
    last_level = 3
    last_kills = 4

    @staticmethod
    def screen_type(frame, cfg) -> str:
        return "PLAY"

    @staticmethod
    def state_summary(frame) -> dict:
        return {"hp": 100, "screen": "PLAY"}

    @staticmethod
    def read_options(frame) -> list[str]:
        return ["A", "B", "C"]

    @staticmethod
    def detect(frame):
        return [], object()

    @staticmethod
    def hud_state(frame) -> dict:
        return {"hp": 100, "level": 3, "timer": "00:05", "inventory": []}

    @staticmethod
    def to_jpeg(frame) -> bytes:
        return b"jpeg"


class FakeLaunch:
    def __init__(self) -> None:
        self.calls: list[object] = []

    def to_stage_select(self, io, cfg) -> None:
        self.calls.append("to_stage_select")

    def start_run(self, io, cfg) -> None:
        self.calls.append("start_run")

    def select_option(self, io, option, options) -> None:
        self.calls.append(("select_option", option, options))


class FakeWriter:
    def __init__(self, root: str, run_id: str) -> None:
        self.dir = str(Path(root) / run_id)
        Path(self.dir, "keyframes").mkdir(parents=True)
        self.ticks: list[tuple] = []
        self.closed: dict | None = None

    def save_frame(self, data: bytes, keyframe: bool = False, name: str | None = None) -> None:
        folder = "keyframes" if keyframe else "frames"
        path = Path(self.dir, folder, name or "frame.jpg")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def log_tick(self, *args) -> None:
        self.ticks.append(args)

    def log_planner(self, *args) -> None:
        pass

    def close(self, **kwargs) -> None:
        self.closed = kwargs


def fixed_config(root: str) -> dict:
    return {
        "episodes_dir": root,
        "tick_hz": 2,
        "goal_target_survival_s": 0,
        "hyper": False,
        "hurry": False,
        "arcanas": False,
        "limit_break": False,
        "inverse": False,
        "endless": False,
    }


class SpineGameToolsTests(unittest.TestCase):
    def make_tools(self, root: str, controller: FakeController | None = None):
        io = FakeIO()
        controller = controller or FakeController()
        launch = FakeLaunch()
        tools = game_tools.SpineGameTools(
            fixed_config(root),
            io,
            controller,
            launch_module=launch,
            perception_module=FakePerception,
            writer_factory=FakeWriter,
            sleeper=lambda _: None,
        )
        return tools, io, controller, launch

    def test_prepare_requires_every_fixed_modifier_before_touching_the_game(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            config = fixed_config(root)
            del config["hurry"]
            io = FakeIO()
            launch = FakeLaunch()
            tools = game_tools.SpineGameTools(
                config,
                io,
                FakeController(),
                launch_module=launch,
                perception_module=FakePerception,
                writer_factory=FakeWriter,
            )

            result = tools.prepare()

            self.assertFalse(result["verified"])
            self.assertIn("hurry", result["reason"])
            self.assertEqual(launch.calls, [])

    def test_model_proposal_reaches_controller_but_never_io_directly(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            tools, io, controller, _ = self.make_tools(root)

            accepted = tools.submit_direction("NE", latency_ms=321.0)

            self.assertTrue(accepted)
            self.assertEqual(controller.submissions, [("NE", 321.0)])
            self.assertEqual(io.neutralized, 0)

    def test_control_window_is_bounded_by_tick_rate(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            tools, _, controller, _ = self.make_tools(root)
            tools.prepare()

            result = tools.control_window(2.0)

            self.assertTrue(result["safe"])
            self.assertEqual(controller.ticks, 4)

    def test_control_exception_always_neutralizes(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            controller = FakeController(fail_tick=True)
            tools, _, controller, _ = self.make_tools(root, controller)
            tools.prepare()

            with self.assertRaisesRegex(RuntimeError, "tick failed"):
                tools.control_window(2.0)

            self.assertGreaterEqual(controller.neutralized, 1)

    def test_observation_and_evaluation_emit_durable_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            tools, _, _, _ = self.make_tools(root)
            prepared = tools.prepare()

            observation = tools.observe()
            outcome = tools.evaluate("finish a run", prepared["run_id"])

            self.assertEqual(observation["screen_type"], "PLAY")
            self.assertTrue(Path(observation["image_path"]).is_file())
            self.assertEqual(outcome["status"], "achieved")
            self.assertTrue(any(item.endswith("outcome.json") for item in outcome["evidence"]))


if __name__ == "__main__":
    unittest.main()
