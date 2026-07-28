"""Focused safety checks for G0 launch navigation."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "spine"))

import launch  # noqa: E402


class FakeStageIO:
    def __init__(self, ocr_text: str) -> None:
        self.ocr_text = ocr_text
        self.keys: list[str] = []
        self.config: dict[str, str] = {}

    def ocr(self, ocr_config: str = "") -> str:
        return self.ocr_text

    def menu_navigate(self, key: str) -> None:
        self.keys.append(key)


class StartRunTests(unittest.TestCase):
    def test_refuses_to_confirm_a_stage_other_than_the_fixed_eval_stage(self) -> None:
        io = FakeStageIO("Stage Selection Green Acres")
        cfg = {
            "stage": "Mad Forest",
            "hyper": False,
            "hurry": False,
            "arcanas": False,
            "limit_break": False,
            "inverse": False,
            "endless": False,
        }

        with (mock.patch.object(launch, "_block"),
              mock.patch.object(launch, "_press_and_expect",
                                side_effect=AssertionError("must not confirm"))):
            with self.assertRaisesRegex(RuntimeError, "Mad Forest"):
                launch.start_run(io, cfg)

        self.assertEqual(io.keys, [])


class StageSelectionTests(unittest.TestCase):
    def test_searches_with_ocr_checkpoints_until_mad_forest_is_selected(self) -> None:
        io = FakeStageIO("Stage Selection Green Acres")
        cfg = {
            "stage": "Mad Forest",
            "stage_search_directions": ["up"],
            "stage_search_max_steps": 3,
        }

        with mock.patch.object(
            launch,
            "_press_and_expect",
            return_value=("STAGE_SELECT", "Stage Selection Mad Forest"),
        ) as press:
            selected = launch.select_stage(io, cfg)

        self.assertIn("MAD FOREST", selected.upper())
        press.assert_called_once_with(io, "up", {"STAGE_SELECT"}, timeout_s=3.0)


class CharacterSelectionTests(unittest.TestCase):
    def test_searches_until_antonio_is_the_visible_selected_character(self) -> None:
        io = FakeStageIO("Character Selection Zi'Assunta Belpaese")
        cfg = {
            "character": "Antonio",
            "character_search_directions": ["up"],
            "character_search_max_steps": 3,
        }

        with mock.patch.object(
            launch,
            "_press_and_expect",
            return_value=("CHARACTER_SELECT", "Character Selection Antonio"),
        ) as press:
            selected = launch.select_character(io, cfg)

        self.assertIn("ANTONIO", selected.upper())
        press.assert_called_once_with(io, "up", {"CHARACTER_SELECT"}, timeout_s=3.0)

    def test_uses_calibrated_scroll_and_card_clicks_when_the_grid_ocr_omits_antonio(self) -> None:
        class CalibratedIO(FakeStageIO):
            def click_frame(self, x: int, y: int) -> None:
                self.keys.append(f"click:{x},{y}")

            def ocr(self, region=None, ocr_config: str = "") -> str:
                if region == [720, 1200, 1800, 1470]:
                    return "Antonio Belpaese (Legacy)"
                return self.ocr_text

        io = CalibratedIO("Character Selection")
        cfg = {
            "character": "Antonio",
            "character_scroll_top_frame": [1786, 355],
            "character_target_frame": [1137, 379],
            "character_selected_label_region": [720, 1200, 1800, 1470],
        }

        with mock.patch.object(launch.time, "sleep"):
            selected = launch.select_character(io, cfg)

        self.assertEqual(selected, "ANTONIO BELPAESE (LEGACY)")
        self.assertEqual(io.keys, ["click:1786,355", "click:1137,379"])


class MainMenuTests(unittest.TestCase):
    def test_dismisses_the_photosensitivity_warning_before_menu_navigation(self) -> None:
        io = FakeStageIO("Photosensitivity warning")
        cfg = {"steam_app_id": "1794680"}

        with (mock.patch.object(launch, "launch_game"),
              mock.patch.object(launch, "_block"),
              mock.patch.object(launch, "_wait_for_state", return_value=("WARNING", "warning")),
              mock.patch.object(
                  launch,
                  "_press_and_expect",
                  side_effect=[("WARNING", "warning"), ("MAIN_MENU", "start")],
              ) as press):
            state, _ = launch.ensure_main_menu(io, cfg)

        self.assertEqual(state, "MAIN_MENU")
        self.assertEqual(press.call_count, 2)
        self.assertIn(
            mock.call(
                io,
                "confirm",
                {"WARNING", "TITLE", "MAIN_MENU", "CHARACTER_SELECT", "STAGE_SELECT"},
            ),
            press.call_args_list,
        )


class ScreenClassificationTests(unittest.TestCase):
    def test_recognizes_the_live_character_grid_when_only_newer_character_names_ocr(self) -> None:
        io = FakeStageIO("Rockstar 28029 Ramba Ambrojoe")

        state, _ = launch.classify_screen(io)

        self.assertEqual(state, "CHARACTER_SELECT")

    def test_recognizes_level_up_before_generic_timer_match(self) -> None:
        io = FakeStageIO("LEVEL UP Whip Garlic 00:16")

        state, _ = launch.classify_screen(io)

        self.assertEqual(state, "LEVEL_UP")

    def test_recognizes_noisy_title_ocr_as_title(self) -> None:
        io = FakeStageIO(
            '(2) ROCKSTAR A A. 28029 VAMPIRE "="S" SURVIVORS '
            "FIRSTSURVIVATON CREDITS"
        )

        state, _ = launch.classify_screen(io)

        self.assertEqual(state, "TITLE")

    def test_recognizes_noisy_character_stats_panel_as_character_select(self) -> None:
        io = FakeStageIO(
            "ROCKSTAR 28029 +36% +40% +21% TAL"
        )

        state, _ = launch.classify_screen(io)

        self.assertEqual(state, "CHARACTER_SELECT")


class AttachLiveTests(unittest.TestCase):
    def test_attaches_to_in_game_and_records_modifier_baseline(self) -> None:
        class AttachIO(FakeStageIO):
            def __init__(self) -> None:
                super().__init__("HP 100 Level 2 00:16")
                self.neutralized = 0

            def neutralize(self) -> None:
                self.neutralized += 1

        io = AttachIO()
        cfg = {
            "hyper": False,
            "hurry": False,
            "arcanas": False,
            "limit_break": False,
            "inverse": False,
            "endless": False,
        }

        result = launch.attach_live(io, cfg)

        self.assertTrue(result["attached"])
        self.assertEqual(result["state"], "IN_GAME")
        self.assertEqual(result["modifiers"]["hurry"], False)
        self.assertEqual(io.neutralized, 1)

    def test_refuses_to_attach_on_menu_screens(self) -> None:
        class AttachIO(FakeStageIO):
            def neutralize(self) -> None:
                pass

        io = AttachIO("Character Selection Antonio")

        with self.assertRaisesRegex(RuntimeError, "already-live"):
            launch.attach_live(
                io,
                {
                    "hyper": False,
                    "hurry": False,
                    "arcanas": False,
                    "limit_break": False,
                    "inverse": False,
                    "endless": False,
                },
            )


if __name__ == "__main__":
    unittest.main()
