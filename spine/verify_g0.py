"""G0 verifier: launch, capture, keys, then vision-led menu entry + movement.

Menu navigation is no longer an OCR macro. After plumbing checks pass, this
runs a bounded LangGraph goal so the vision leader reaches an in-game HUD.
"""

from __future__ import annotations

import json
import os
import time
import uuid

import cv2
import numpy as np
import yaml

import launch
from io_adapter import IOAdapter


def pixel_diff(before, after) -> float:
    return float(np.mean(np.abs(before.astype(np.float32) - after.astype(np.float32))) / 255.0)


def _active_blocker() -> bool:
    path = "status/BLOCKED.md"
    if not os.path.exists(path):
        return False
    with open(path, encoding="utf-8") as status:
        first_line = status.readline().upper()
    return "CLEARED" not in first_line


def _append_evidence(results: dict, evidence: dict) -> None:
    verdict = "PASSED" if all(value == "PASS" for value in results.values()) else "FAILED"
    with open("status/gates.md", "a", encoding="utf-8") as gates:
        gates.write(f"\n## G0 Plumbing Gate — {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        gates.write(f"**Verdict:** {verdict}\n\n**Results:**\n")
        for check, outcome in results.items():
            gates.write(f"- {check}: {outcome}\n")
        gates.write("\n**Evidence:**\n")
        for key, value in evidence.items():
            gates.write(f"- {key}: {value}\n")


def _vision_menu_entry(cfg: dict, evidence: dict) -> None:
    """Bounded vision-led entry; OCR must not own the menu route."""
    from run import run_langgraph_goal

    thread_id = f"g0-vision-entry-{uuid.uuid4().hex[:8]}"
    goal = (
        "Reach an in-game Mad Forest HUD as Antonio with hyper/hurry/arcanas/"
        "limit_break/inverse/endless all false. Stop once the run has started; "
        "survival target for this plumbing check is 0 seconds of scored play."
    )
    # Temporarily allow immediate evaluate success after entry by using a
    # short-lived tools evaluate target via config copy.
    state = run_langgraph_goal(
        goal,
        thread_id=thread_id,
        retries=0,
        checkpoint_path="runtime/langgraph-g0-vision.sqlite3",
        config_path="spine/config.yaml",
        attach=False,
        entry_only=True,
    )
    evidence["vision_thread_id"] = thread_id
    evidence["vision_status"] = state.get("status")
    evidence["vision_reason"] = state.get("reason")
    evidence["vision_evidence"] = state.get("evidence")
    if state.get("status") == "blocked":
        raise RuntimeError(f"vision menu entry blocked: {state.get('reason')}")


def verify_g0() -> bool:
    cfg = None
    io = None
    results, evidence = {}, {}
    try:
        cfg = yaml.safe_load(open("spine/config.yaml", encoding="utf-8"))
        if _active_blocker():
            results["blocked"] = "BLOCKED"
            evidence["blocked_status"] = "status/BLOCKED.md is active"
            raise RuntimeError("active status/BLOCKED.md prevents game interaction")
        io = IOAdapter(backend=os.environ.get("VS_IO_BACKEND", "auto"), config=cfg)

        launched = launch.launch_game(cfg, io)
        # Wait briefly for a window; vision entry owns further navigation.
        deadline = time.monotonic() + 45.0
        while time.monotonic() < deadline and io._game_window() is None:
            time.sleep(0.5)
        if io._game_window() is None:
            raise RuntimeError("game window not available after launch")
        results["launch"] = "PASS"
        evidence["launched_process"] = launched

        frame = io.screenshot()
        cv2.imwrite("status/g0_capture.jpg", frame.image)
        results["capture"] = "PASS"
        evidence["capture_resolution"] = f"{frame.width}x{frame.height}"
        evidence["capture_mean_brightness"] = round(float(frame.image.mean()), 2)

        before = io.screenshot()
        try:
            io.menu_navigate("down")
            time.sleep(0.5)
            after = io.screenshot()
            diff = pixel_diff(before.image, after.image)
        finally:
            io.menu_navigate("up")
        if diff <= cfg.get("key_diff_threshold", 0.02):
            raise RuntimeError(f"menu highlight diff too low: {diff:.4f}")
        results["keys"] = "PASS"
        evidence["key_diff"] = round(diff, 4)

        # Close plumbing IO before the LangGraph path opens its own adapter.
        io.close()
        io = None

        # Vision leader navigates menus; OCR is not the menu authority.
        evidence["menu_authority"] = "vision-leader"
        _vision_menu_entry(cfg, evidence)
        results["vision_menu"] = "PASS"

        # Movement proof after vision entry: reopen IO against the live window.
        io = IOAdapter(backend=os.environ.get("VS_IO_BACKEND", "auto"), config=cfg)
        start = io.screenshot()
        cv2.imwrite("status/g0_move_before.jpg", start.image)
        io.hold_direction("E")
        time.sleep(2.0)
        end = io.screenshot()
        io.neutralize()
        cv2.imwrite("status/g0_move_after.jpg", end.image)
        movement = pixel_diff(start.image, end.image)
        if movement <= cfg.get("movement_diff_threshold", 0.1):
            raise RuntimeError(f"in-game camera diff too low: {movement:.4f}")
        results["move"] = "PASS"
        evidence["movement_diff"] = round(movement, 4)
        evidence["movement_hold_s"] = 2.0
        evidence["move_before"] = "status/g0_move_before.jpg"
        evidence["move_after"] = "status/g0_move_after.jpg"
    except Exception as error:
        if "blocked" not in results:
            failed = next(
                (
                    name
                    for name in ("launch", "capture", "keys", "vision_menu", "move")
                    if name not in results
                ),
                "unknown",
            )
            results[failed] = f"FAIL ({error})"
    finally:
        if io is not None:
            io.close()
        _append_evidence(results, evidence)

    print(json.dumps({"results": results, "evidence": evidence}, indent=2))
    return all(value == "PASS" for value in results.values())


if __name__ == "__main__":
    raise SystemExit(0 if verify_g0() else 1)
