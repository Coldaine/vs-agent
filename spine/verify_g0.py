"""verify_g0.py — Dedicated G0 Plumbing Gate Verifier.

Tests:
1. LAUNCH: Steam starts VS.
2. CAPTURE: Not black frames (WGC/DXCam).
3. KEYS: Send 'down', verify menu diff.
4. MENU MACRO: Macro reaches Stage Select.
5. MOVE CHECK: Movement changes background (camera-locked to player).
"""

from __future__ import annotations
import argparse, json, os, sys, time
import numpy as np
import yaml
import perceive
import launch
from io_adapter import IOAdapter

def get_pixel_diff(img1, img2):
    """Return mean absolute pixel difference between two images."""
    return np.mean(np.abs(img1.astype(float) - img2.astype(float)))

def verify_g0():
    cfg = yaml.safe_load(open("spine/config.yaml"))
    io = IOAdapter(backend=os.environ.get("VS_IO_BACKEND", "auto"), config=cfg)
    results = {}
    evidence = {}

    print("[G0] Starting Plumbing Verification...")

    # 1. Capture Check
    print("[G0] Verifying Capture...")
    launch.launch_game(cfg, io)
    try:
        f1 = io.screenshot()
        if f1 is None or f1.image is None:
            results["capture"] = "FAIL (No frame)"
        elif np.mean(f1.image) < 2:
            results["capture"] = "FAIL (Black frame)"
        else:
            results["capture"] = "PASS"
            evidence["capture_resolution"] = f"{f1.width}x{f1.height}"
            evidence["capture_mean_brightness"] = float(np.mean(f1.image))
            # Save first frame as evidence
            import cv2
            cv2.imwrite("status/g0_capture.jpg", f1.image)
    except Exception as e:
        results["capture"] = f"FAIL ({e})"

    # 2. Key Check (Menu Diff with one retry)
    print("[G0] Verifying Keys...")
    try:
        f_before = io.screenshot()
        io.menu_navigate("down")  # Use menu_navigate instead of key_hold
        time.sleep(0.5)
        f_after = io.screenshot()
        diff = get_pixel_diff(f_before.image, f_after.image)
        
        if diff > 1.0:  # Menu highlight changed
            results["keys"] = "PASS"
            evidence["key_diff"] = float(diff)
        else:
            # One retry
            time.sleep(0.5)
            io.menu_navigate("down")
            time.sleep(0.5)
            f_retry = io.screenshot()
            diff_retry = get_pixel_diff(f_after.image, f_retry.image)
            if diff_retry > 1.0:
                results["keys"] = "PASS"
                evidence["key_diff"] = float(diff_retry)
            else:
                results["keys"] = f"FAIL (Diff too low: {diff:.2f}, retry: {diff_retry:.2f})"
    except Exception as e:
        results["keys"] = f"FAIL ({e})"

    # 3. Macro Check
    print("[G0] Verifying Menu Macro...")
    try:
        launch.to_stage_select(io, cfg)
        f_stage = io.screenshot()
        results["macro"] = "PASS"  # launch.py throws if OCR fails
        evidence["reached_stage_select"] = True
    except Exception as e:
        results["macro"] = f"FAIL ({e})"
        evidence["reached_stage_select"] = False

    # 4. Move Check (camera displacement, not player coords)
    print("[G0] Verifying Movement...")
    try:
        launch.start_run(io, cfg)
        time.sleep(2)  # Initial spawn
        f_start = io.screenshot()
        
        # Hold direction for movement (camera-locked, so background changes)
        io.hold_direction("E")  # Use hold_direction instead of key_hold
        time.sleep(1.0)
        f_end = io.screenshot()
        io.neutralize()
        
        move_diff = get_pixel_diff(f_start.image, f_end.image)
        if move_diff > 5.0:  # Background moved
            results["move"] = "PASS"
            evidence["move_diff"] = float(move_diff)
        else:
            results["move"] = f"FAIL (Diff too low: {move_diff:.2f})"
            
    except Exception as e:
        results["move"] = f"FAIL ({e})"
    finally:
        io.neutralize()

    # Write gate evidence
    print("\n[G0] Summary:")
    print(json.dumps(results, indent=2))
    
    gate_passed = all(v == "PASS" for v in results.values())
    verdict = "PASSED" if gate_passed else "FAILED"
    
    # Append to status/gates.md
    with open("status/gates.md", "a") as f:
        f.write(f"\n## G0 Plumbing Gate — {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"**Verdict:** {verdict}\n\n")
        f.write("**Results:**\n")
        for test, outcome in results.items():
            f.write(f"- {test}: {outcome}\n")
        f.write("\n**Evidence:**\n")
        for key, val in evidence.items():
            f.write(f"- {key}: {val}\n")
        f.write("\n")
    
    print(f"\nG0 PLUMBING {verdict}")
    print(f"Evidence written to status/gates.md")
    
    return gate_passed

if __name__ == "__main__":
    verify_g0()
