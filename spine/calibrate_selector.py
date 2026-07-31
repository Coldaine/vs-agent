"""Evidence-first calibration for Vampire Survivors' pre-run selector.

The default mode only captures a frame and OCR word boxes.  Input is opt-in
and deliberately limited to the two non-confirming clicks needed to select
the calibrated Antonio card.  Stage selection remains capture-only until it
has its own verified route.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from pathlib import Path

def action_plan(action: str, cfg: dict) -> list[tuple[str, tuple[int, int] | str]]:
    """Return the exact permitted input plan; capture/stage modes never input."""
    if action in {"capture", "select-stage"}:
        return []
    if action == "select-character":
        return [
            ("click", tuple(cfg["character_scroll_top_frame"])),
            ("click", tuple(cfg["character_target_frame"])),
        ]
    raise ValueError(f"unsupported calibration action: {action}")


def target_card_has_focus(image, cfg: dict, *, patch_size: int = 5,
                          bright_threshold: int = 230) -> bool:
    """Prove focus from all four white corner brackets of the target card."""
    x, y, width, height = cfg["character_target_rect"]
    corners = ((x, y), (x + width, y), (x, y + height), (x + width, y + height))
    for corner_x, corner_y in corners:
        bright = 0
        for row in range(corner_y, corner_y + patch_size):
            for column in range(corner_x, corner_x + patch_size):
                try:
                    pixel = image[row][column]
                except (IndexError, TypeError):
                    return False
                if min(int(value) for value in pixel) >= bright_threshold:
                    bright += 1
        if bright < patch_size:
            return False
    return True


def target_card_focus_changed(before, after, cfg: dict, *, patch_size: int = 5,
                              delta_threshold: int = 60) -> bool:
    """Verify that a click changed all four target-card focus-corner patches."""
    x, y, width, height = cfg["character_target_rect"]
    corners = ((x, y), (x + width, y), (x, y + height), (x + width, y + height))
    for corner_x, corner_y in corners:
        changed = 0
        for row in range(corner_y, corner_y + patch_size):
            for column in range(corner_x, corner_x + patch_size):
                try:
                    before_pixel = before[row][column]
                    after_pixel = after[row][column]
                except (IndexError, TypeError):
                    return False
                if max(abs(int(old) - int(new)) for old, new in zip(before_pixel, after_pixel)) >= delta_threshold:
                    changed += 1
        if changed < patch_size:
            return False
    return True


def write_snapshot(io: IOAdapter, output_dir: Path, label: str) -> dict:
    """Capture frame plus OCR word boxes and a content hash for later review."""
    import cv2
    import pytesseract
    from launch import classify_screen

    output_dir.mkdir(parents=True, exist_ok=True)
    frame = io.screenshot()
    stamp = time.strftime("%Y%m%d-%H%M%S")
    image_path = output_dir / f"{stamp}-{label}.jpg"
    cv2.imwrite(str(image_path), frame.image)
    if io.config.get("tesseract_cmd"):
        pytesseract.pytesseract.tesseract_cmd = io.config["tesseract_cmd"]
    words = pytesseract.image_to_data(
        frame.image, config="--psm 11", output_type=pytesseract.Output.DICT)
    record = {
        "label": label,
        "image": str(image_path),
        "sha256": hashlib.sha256(frame.image.tobytes()).hexdigest(),
        "resolution": [frame.width, frame.height],
        "state": classify_screen(io)[0],
        "ocr_words": [
            {key: words[key][index] for key in ("text", "left", "top", "width", "height", "conf")}
            for index, text in enumerate(words["text"])
            if text.strip()
        ],
    }
    (output_dir / f"{stamp}-{label}.json").write_text(
        json.dumps(record, indent=2), encoding="utf-8")
    return record


def run(action: str, cfg: dict, output_dir: Path) -> list[dict]:
    """Execute one explicit calibration action with before/after evidence."""
    import cv2
    from io_adapter import IOAdapter

    io = IOAdapter(backend=os.environ.get("VS_IO_BACKEND", "auto"), config=cfg)
    try:
        records = [write_snapshot(io, output_dir, f"before-{action}")]
        for kind, value in action_plan(action, cfg):
            if kind != "click":
                raise RuntimeError(f"disallowed calibration action {kind!r}")
            io.click_frame(*value)
            time.sleep(0.35)
        records.append(write_snapshot(io, output_dir, f"after-{action}"))
        if action == "select-character":
            before = cv2.imread(records[0]["image"])
            after = cv2.imread(records[1]["image"])
            if before is None or after is None or not target_card_focus_changed(before, after, cfg):
                raise RuntimeError("Antonio card focus proof was not observed; refusing to advance")
        return records
    finally:
        io.close()


def main() -> int:
    import yaml

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--action", choices=("capture", "select-character", "select-stage"), default="capture")
    parser.add_argument("--output-dir", default="status/selector_calibration")
    args = parser.parse_args()
    cfg = yaml.safe_load(Path("spine/config.yaml").read_text(encoding="utf-8"))
    print(json.dumps(run(args.action, cfg, Path(args.output_dir)), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
