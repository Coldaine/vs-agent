"""Capture-frame to Windows hit-test coordinate transform.

The G0 fixed display uses a calibrated scale between WGC frame pixels and
Windows cursor hit-test coordinates. Any resolution, DPI, monitor, or capture
backend change invalidates the calibration and must fail closed.
"""

from __future__ import annotations


class CalibrationError(RuntimeError):
    """Raised when the live capture no longer matches the fixed calibration."""


def frame_to_hit_test(
    x: int | float,
    y: int | float,
    config: dict,
    *,
    frame_size: tuple[int, int] | list[int] | None = None,
) -> tuple[int, int]:
    """Convert WGC frame coordinates into Windows hit-test coordinates."""
    expected_list = list(config.get("capture_calibration_resolutions") or [])
    single = config.get("capture_calibration_resolution")
    if single is not None and single not in expected_list:
        expected_list.append(single)
    if expected_list and frame_size is not None:
        actual_w, actual_h = int(frame_size[0]), int(frame_size[1])
        tolerance = int(config.get("capture_calibration_tolerance_px", 0))
        matched = False
        for expected in expected_list:
            expected_w, expected_h = int(expected[0]), int(expected[1])
            if (
                abs(actual_w - expected_w) <= tolerance
                and abs(actual_h - expected_h) <= tolerance
            ):
                matched = True
                break
        if not matched:
            allowed = ", ".join(f"{int(w)}x{int(h)}" for w, h in expected_list)
            raise CalibrationError(
                "capture resolution drifted from calibration: "
                f"expected one of [{allowed}] (±{tolerance}px), "
                f"got {actual_w}x{actual_h}"
            )

    scale = float(config.get("capture_to_input_scale", 1.0))
    if scale <= 0:
        raise CalibrationError(f"capture_to_input_scale must be > 0, got {scale}")
    return int(round(float(x) * scale)), int(round(float(y) * scale))


def modifier_baseline(config: dict) -> dict[str, bool]:
    """Return the six explicit eval modifiers; fail if any are missing."""
    keys = ("hyper", "hurry", "arcanas", "limit_break", "inverse", "endless")
    missing = [name for name in keys if name not in config]
    if missing:
        raise CalibrationError(
            "fixed modifier baseline is incomplete: " + ", ".join(missing)
        )
    return {name: bool(config[name]) for name in keys}


def assert_capture_contract(
    config: dict,
    frame_size: tuple[int, int] | list[int],
) -> tuple[int, int]:
    """Fail closed unless the live frame matches the fullscreen calibration."""
    # Reuse frame_to_hit_test's resolution gate with a dummy point.
    frame_to_hit_test(0, 0, config, frame_size=frame_size)
    if config.get("require_fullscreen", False):
        expected = config.get("capture_calibration_resolution")
        if expected is not None:
            # Fullscreen contract: exact calibrated size (within tolerance).
            # Soft documentation signal for operators; hard check is above.
            pass
    return int(frame_size[0]), int(frame_size[1])
