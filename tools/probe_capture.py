"""Live capture probe: does the runtime's capture layer see the running game?

No model calls, no game input, no screen takeover. Reports frame size,
brightness, and whether it satisfies the configured capture contract.
"""
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent / "spine"))

from io_adapter import IOAdapter  # noqa: E402


def main() -> int:
    cfg = yaml.safe_load(
        (Path(__file__).resolve().parent / "spine" / "config.yaml").read_text(
            encoding="utf-8"
        )
    )
    print("config capture_backend:", cfg.get("capture_backend"))
    print("config expected resolution:", cfg.get("capture_calibration_resolution"))
    print("config wgc_monitor_origin:", cfg.get("wgc_monitor_origin"))
    print("config capture_output_idx:", cfg.get("capture_output_idx"))
    io = None
    try:
        io = IOAdapter(backend="wgc", config=cfg)
        frame = io.screenshot()
        print("capture OK: size =", frame.width, "x", frame.height)
        img = getattr(frame, "image", None)
        if img is not None:
            import numpy as np

            print("mean brightness:", round(float(np.mean(img)), 2))
        from capture_transform import assert_capture_contract

        try:
            assert_capture_contract(cfg, (frame.width, frame.height))
            print("contract: PASS")
        except Exception as error:  # noqa: BLE001
            print("contract: FAIL ->", error)
        return 0
    except Exception as error:  # noqa: BLE001
        print("capture probe FAILED:", type(error).__name__, error)
        return 1
    finally:
        if io is not None:
            io.close()


if __name__ == "__main__":
    raise SystemExit(main())
