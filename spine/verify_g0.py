"""G0 verifier: launch, WGC capture, keys, menu macro, and movement."""

from __future__ import annotations

import json
import os
import time

import cv2
import numpy as np
import yaml

import launch
from io_adapter import IOAdapter


def pixel_diff(before, after) -> float:
    return float(np.mean(np.abs(before.astype(np.float32) - after.astype(np.float32))))


def _append_evidence(results: dict, evidence: dict) -> None:
    verdict = "PASSED" if all(value == "PASS" for value in results.values()) else "FAILED"
    with open("status/gates.md", "a", encoding="utf-8") as gates:
        gates.write(f"\n## G0 Plumbing Gate — {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        gates.write(f"**Verdict:** {verdict}\n\n**Results:**\n")
        for check, outcome in results.items():
            gates.write(f"- {check}: {outcome}\n")
        gates.write("\n**Evidence:**\n")
        for key, value in evidence.items():
            gates.write(f"- {key}: {value}\n")


def verify_g0() -> bool:
    cfg = yaml.safe_load(open("spine/config.yaml", encoding="utf-8"))
    io = IOAdapter(backend=os.environ.get("VS_IO_BACKEND", "auto"), config=cfg)
    results, evidence = {}, {}
    try:
        # Launch is idempotent; ensure_main_menu also proves keyboard navigation.
        launched = launch.launch_game(cfg, io)
        launch.ensure_main_menu(io, cfg)
        results["launch"] = "PASS"
        evidence["launched_process"] = launched

        frame = io.screenshot()
        cv2.imwrite("status/g0_capture.jpg", frame.image)
        results["capture"] = "PASS"
        evidence["capture_resolution"] = f"{frame.width}x{frame.height}"
        evidence["capture_mean_brightness"] = round(float(frame.image.mean()), 2)

        before = io.screenshot()
        before_text = io.ocr()[:180].replace("\n", " ")
        io.menu_navigate("down")
        time.sleep(0.5)
        after = io.screenshot()
        after_text = io.ocr()[:180].replace("\n", " ")
        diff = pixel_diff(before.image, after.image)
        # Restore the original menu highlight after the required DOWN check.
        io.menu_navigate("up")
        if diff <= cfg.get("key_diff_threshold", 0.02):
            raise RuntimeError(f"main-menu highlight diff too low: {diff:.4f}")
        results["keys"] = "PASS"
        evidence["key_diff"] = round(diff, 4)
        evidence["key_ocr_before"] = before_text
        evidence["key_ocr_after"] = after_text

        launch.to_stage_select(io, cfg)
        results["menu_macro"] = "PASS"
        evidence["stage_text"] = launch.classify_screen(io)[1][:180]

        launch.start_run(io, cfg)
        start = io.screenshot()
        io.hold_direction("E")
        time.sleep(1.0)
        end = io.screenshot()
        io.neutralize()
        movement = pixel_diff(start.image, end.image)
        if movement <= cfg.get("movement_diff_threshold", 0.1):
            raise RuntimeError(f"in-game camera diff too low: {movement:.4f}")
        results["move"] = "PASS"
        evidence["movement_diff"] = round(movement, 4)
    except Exception as error:
        failed = next((name for name in ("launch", "capture", "keys", "menu_macro", "move")
                       if name not in results), "unknown")
        results[failed] = f"FAIL ({error})"
    finally:
        io.close()
        _append_evidence(results, evidence)

    print(json.dumps({"results": results, "evidence": evidence}, indent=2))
    return all(value == "PASS" for value in results.values())


if __name__ == "__main__":
    verify_g0()
