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
        self.menu_keys: list[str] = []
        self.clicks: list[tuple[int, int]] = []

    def screenshot(self) -> FakeFrame:
        return FakeFrame()

    def ocr(self, region=None, ocr_config: str = "") -> str:
        return "Character Selection Antonio"

    def menu_navigate(self, key: str) -> None:
        self.menu_keys.append(key)

    def click_frame(self, x: int, y: int) -> None:
        self.clicks.append((x, y))

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
    def __init__(self, classify: str = "CHARACTER_SELECT") -> None:
        self.calls: list[object] = []
        self.classify = classify

    def launch_game(self, cfg, io=None) -> bool:
        self.calls.append("launch_game")
        return True

    def to_stage_select(self, io, cfg) -> None:
        self.calls.append("to_stage_select")

    def start_run(self, io, cfg) -> None:
        self.calls.append("start_run")

    def attach_live(self, io, cfg) -> dict:
        self.calls.append("attach_live")
        return {
            "attached": True,
            "state": "IN_GAME",
            "modifiers": {
                "hyper": False,
                "hurry": False,
                "arcanas": False,
                "limit_break": False,
                "inverse": False,
                "endless": False,
            },
            "ocr": "00:16",
        }

    def classify_screen(self, io) -> tuple[str, str]:
        return self.classify, "hint text"

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
        "menu_steps_budget": 40,
        "menu_action_settle_s": 0.0,
        "capture_contract_wait_s": 0.0,
        "require_fullscreen": True,
        "capture_to_input_scale": 1.0,
        "capture_calibration_resolution": [100, 100],
        "capture_calibration_tolerance_px": 0,
        "character": "Antonio",
        "stage": "Mad Forest",
        "hyper": False,
        "hurry": False,
        "arcanas": False,
        "limit_break": False,
        "inverse": False,
        "endless": False,
        "steam_app_id": "1794680",
    }


class SpineGameToolsTests(unittest.TestCase):
    def make_tools(
        self,
        root: str,
        controller: FakeController | None = None,
        *,
        attach: bool = False,
        entry_only: bool = False,
        classify: str = "CHARACTER_SELECT",
    ):
        io = FakeIO()
        controller = controller or FakeController()
        launch = FakeLaunch(classify=classify)
        tools = game_tools.SpineGameTools(
            fixed_config(root),
            io,
            controller,
            attach=attach,
            entry_only=entry_only,
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

    def test_prepare_launches_without_ocr_menu_macro(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            tools, _, _, launch = self.make_tools(root)

            prepared = tools.prepare()

            self.assertTrue(prepared["verified"])
            self.assertEqual(launch.calls, ["launch_game"])
            self.assertNotIn("to_stage_select", launch.calls)
            self.assertNotIn("start_run", launch.calls)

    def test_prepare_fails_closed_when_capture_is_not_fullscreen_calibration(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            config = fixed_config(root)
            config["capture_calibration_resolution"] = [2560, 1440]
            io = FakeIO()
            launch = FakeLaunch()
            tools = game_tools.SpineGameTools(
                config,
                io,
                FakeController(),
                launch_module=launch,
                perception_module=FakePerception,
                writer_factory=FakeWriter,
                sleeper=lambda _: None,
            )

            prepared = tools.prepare()

            self.assertFalse(prepared["verified"])
            self.assertIn("fullscreen", prepared["reason"].lower())

    def test_attach_prepare_skips_menu_macro_and_records_modifiers(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            tools, _, _, launch = self.make_tools(root, attach=True)

            prepared = tools.prepare()

            self.assertTrue(prepared["verified"])
            self.assertTrue(prepared["attached"])
            self.assertEqual(prepared["attach_state"], "IN_GAME")
            self.assertEqual(prepared["modifiers"]["arcanas"], False)
            self.assertEqual(launch.calls, ["attach_live"])
            self.assertTrue(tools.in_game)

    def test_observe_works_before_in_game_and_marks_ocr_as_hint(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            tools, _, _, _ = self.make_tools(root, classify="CHARACTER_SELECT")
            tools.prepare()

            observation = tools.observe()

            self.assertEqual(observation["screen_type"], "MENU")
            self.assertEqual(observation["screen_guess"], "CHARACTER_SELECT")
            self.assertTrue(observation["hints_are_non_authoritative"])
            self.assertTrue(Path(observation["image_path"]).is_file())

    def test_menu_action_uses_io_not_controller_movement(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            tools, io, controller, _ = self.make_tools(root)
            tools.prepare()

            result = tools.menu_action("down")

            self.assertTrue(result["ok"])
            self.assertEqual(io.menu_keys, ["down"])
            self.assertEqual(controller.submissions, [])

    def test_menu_action_click_goes_through_click_frame(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            tools, io, controller, _ = self.make_tools(root)
            tools.prepare()

            tools.menu_action("click", click=[100, 200])

            self.assertEqual(io.clicks, [(100, 200)])
            self.assertEqual(controller.submissions, [])

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

    def test_entry_only_evaluate_succeeds_after_in_game(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            tools, _, _, _ = self.make_tools(
                root, entry_only=True, classify="IN_GAME"
            )
            prepared = tools.prepare()
            tools.observe()

            outcome = tools.evaluate_entry(prepared["run_id"])

            self.assertEqual(outcome["status"], "achieved")
            self.assertIn("in-game", outcome["reason"])


if __name__ == "__main__":
    unittest.main()
