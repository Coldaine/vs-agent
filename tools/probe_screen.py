"""Classify the current live game screen. OCR only, no input."""
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent / "spine"))

from io_adapter import IOAdapter  # noqa: E402
from launch import classify_screen  # noqa: E402


def main() -> int:
    cfg = yaml.safe_load(
        (Path(__file__).resolve().parent / "spine" / "config.yaml").read_text(
            encoding="utf-8"
        )
    )
    io = None
    try:
        io = IOAdapter(backend="wgc", config=cfg)
        frame = io.screenshot()
        import cv2

        out = Path(__file__).resolve().parent / "status" / "probe_current.jpg"
        cv2.imwrite(str(out), frame.image)
        state, text = classify_screen(io)
        print("state:", state)
        print("ocr_text:", text[:400])
        print("saved:", out)
        return 0
    except Exception as error:  # noqa: BLE001
        print("probe FAILED:", type(error).__name__, error)
        return 1
    finally:
        if io is not None:
            io.close()


if __name__ == "__main__":
    raise SystemExit(main())
