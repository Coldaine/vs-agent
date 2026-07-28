"""Safety tests for the selector-calibration tool."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "spine"))

import calibrate_selector  # noqa: E402


class ActionPlanTests(unittest.TestCase):
    def setUp(self) -> None:
        self.cfg = {
            "character_scroll_top_frame": [1786, 355],
            "character_target_frame": [1137, 379],
        }

    def test_capture_mode_never_emits_input(self) -> None:
        self.assertEqual(calibrate_selector.action_plan("capture", self.cfg), [])

    def test_character_mode_only_clicks_the_calibrated_grid_controls(self) -> None:
        self.assertEqual(
            calibrate_selector.action_plan("select-character", self.cfg),
            [("click", (1786, 355)), ("click", (1137, 379))],
        )


class FocusProofTests(unittest.TestCase):
    def test_requires_all_four_bright_selection_corners(self) -> None:
        image = [[[0, 0, 0] for _ in range(100)] for _ in range(100)]
        cfg = {"character_target_rect": [20, 20, 40, 40]}
        for x, y in ((20, 20), (60, 20), (20, 60), (60, 60)):
            for row in range(y, y + 5):
                for column in range(x, x + 5):
                    image[row][column] = [255, 255, 255]

        self.assertTrue(calibrate_selector.target_card_has_focus(image, cfg))

    def test_rejects_a_card_without_all_selection_corners(self) -> None:
        image = [[[0, 0, 0] for _ in range(100)] for _ in range(100)]
        cfg = {"character_target_rect": [20, 20, 40, 40]}
        for x, y in ((20, 20), (60, 20), (20, 60)):
            for row in range(y, y + 5):
                for column in range(x, x + 5):
                    image[row][column] = [255, 255, 255]

        self.assertFalse(calibrate_selector.target_card_has_focus(image, cfg))

    def test_proves_focus_by_the_expected_four_corner_deltas(self) -> None:
        before = [[[0, 0, 0] for _ in range(100)] for _ in range(100)]
        after = [[[0, 0, 0] for _ in range(100)] for _ in range(100)]
        cfg = {"character_target_rect": [20, 20, 40, 40]}
        for x, y in ((20, 20), (60, 20), (20, 60), (60, 60)):
            for row in range(y, y + 5):
                for column in range(x, x + 5):
                    after[row][column] = [200, 200, 200]

        self.assertTrue(calibrate_selector.target_card_focus_changed(before, after, cfg))

    def test_stage_selection_mode_cannot_emit_confirm(self) -> None:
        self.assertNotIn(
            ("menu", "confirm"),
            calibrate_selector.action_plan("select-stage", {}),
        )


if __name__ == "__main__":
    unittest.main()
