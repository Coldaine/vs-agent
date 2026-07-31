"""Calibration contract for capture-to-hit-test transforms."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "spine"))

import capture_transform  # noqa: E402


class FrameToHitTestTests(unittest.TestCase):
    def test_applies_the_calibrated_1_25x_scale(self) -> None:
        hit = capture_transform.frame_to_hit_test(
            950,
            1090,
            {"capture_to_input_scale": 1.25},
        )

        self.assertEqual(hit, (1188, 1362))

    def test_fails_closed_when_capture_resolution_drifts(self) -> None:
        with self.assertRaisesRegex(
            capture_transform.CalibrationError,
            "capture resolution drifted",
        ):
            capture_transform.frame_to_hit_test(
                10,
                10,
                {
                    "capture_to_input_scale": 1.25,
                    "capture_calibration_resolution": [2562, 1479],
                    "capture_calibration_tolerance_px": 16,
                },
                frame_size=(1920, 1080),
            )

    def test_accepts_matching_calibration_resolution(self) -> None:
        hit = capture_transform.frame_to_hit_test(
            100,
            200,
            {
                "capture_to_input_scale": 1.25,
                "capture_calibration_resolution": [2562, 1479],
            },
            frame_size=(2562, 1479),
        )

        self.assertEqual(hit, (125, 250))

    def test_allows_small_live_height_jitter_within_tolerance(self) -> None:
        hit = capture_transform.frame_to_hit_test(
            100,
            200,
            {
                "capture_to_input_scale": 1.25,
                "capture_calibration_resolution": [2562, 1479],
                "capture_calibration_tolerance_px": 16,
            },
            frame_size=(2562, 1472),
        )

        self.assertEqual(hit, (125, 250))

    def test_accepts_any_listed_calibration_resolution(self) -> None:
        hit = capture_transform.frame_to_hit_test(
            100,
            200,
            {
                "capture_to_input_scale": 1.25,
                "capture_calibration_resolutions": [
                    [2560, 1380],
                    [2562, 1479],
                ],
            },
            frame_size=(2562, 1479),
        )

        self.assertEqual(hit, (125, 250))


class ModifierBaselineTests(unittest.TestCase):
    def test_requires_all_six_explicit_modifiers(self) -> None:
        with self.assertRaisesRegex(
            capture_transform.CalibrationError,
            "hurry",
        ):
            capture_transform.modifier_baseline(
                {
                    "hyper": False,
                    "arcanas": False,
                    "limit_break": False,
                    "inverse": False,
                    "endless": False,
                }
            )

    def test_returns_the_fixed_eval_baseline(self) -> None:
        baseline = capture_transform.modifier_baseline(
            {
                "hyper": False,
                "hurry": False,
                "arcanas": False,
                "limit_break": False,
                "inverse": False,
                "endless": False,
            }
        )

        self.assertEqual(
            baseline,
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
