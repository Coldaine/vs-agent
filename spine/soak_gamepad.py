"""soak_gamepad.py — empirical ViGEm stability soak.

Creates a virtual Xbox 360 pad, ticks it at ~2 Hz, polls XInputGetState at
1 Hz, and logs every disconnect/recovery to JSONL. Run this in parallel
with development; a zero-drop 30-minute report is the bar before the
gamepad backend is trusted in eval runs (plan's gamepad workstream).

Usage:
  python spine/soak_gamepad.py --minutes 30
"""

from __future__ import annotations

import argparse
import json
import time

from io_adapter import IOAdapter, _connected_xinput_slots

LOG_FILE = "gamepad_soak.jsonl"


def _log(record: dict) -> None:
    with open(LOG_FILE, "a") as f:
        f.write(json.dumps(record) + "\n")


def run_soak(duration_minutes: float = 30.0) -> dict:
    io = IOAdapter("wgc", {"input_backend": "gamepad", "capture_backend": "wgc"})
    baseline_slots = _connected_xinput_slots()
    print(f"[soak] XInput slots connected at start: {sorted(baseline_slots)}")

    start = time.time()
    end = start + duration_minutes * 60
    ticks = polls = drops = 0
    prev_recoveries = 0
    last_poll = 0.0
    _log({"event": "soak_start", "t": start, "slots": sorted(baseline_slots)})

    try:
        while time.time() < end:
            # ~2 Hz tick to keep the device exercised.
            io.hold_direction("N")
            time.sleep(0.25)
            io.hold_direction("HOLD")
            time.sleep(0.25)
            ticks += 1

            now = time.time()
            if now - last_poll >= 1.0:          # 1 Hz XInput poll
                last_poll = now
                polls += 1
                connected = _connected_xinput_slots()
                recoveries = io._gamepad_recoveries
                lost = bool(baseline_slots) and not (baseline_slots & connected)
                if recoveries > prev_recoveries or lost:
                    drops += 1
                    prev_recoveries = recoveries
                    _log({"event": "drop", "t": now,
                          "elapsed_s": round(now - start, 1),
                          "connected": sorted(connected),
                          "recoveries": recoveries})
                    print(f"[soak] DROP at {now - start:.0f}s "
                          f"connected={sorted(connected)} recoveries={recoveries}")
    finally:
        io.close()

    elapsed = time.time() - start
    mtbf_s = round(elapsed / drops, 1) if drops else None
    summary = {"event": "soak_complete", "duration_min": duration_minutes,
               "elapsed_s": round(elapsed, 1), "ticks": ticks, "polls": polls,
               "drops": drops, "mtbf_s": mtbf_s}
    _log(summary)
    print(json.dumps(summary, indent=2))
    return summary


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Soak-test the ViGEm gamepad backend.")
    ap.add_argument("--minutes", type=float, default=30.0,
                    help="Soak duration in minutes (default 30).")
    args = ap.parse_args()
    run_soak(args.minutes)
