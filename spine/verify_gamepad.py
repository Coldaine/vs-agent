"""Verify ViGEm/vgamepad creation and XInput enumeration without launching the game."""

from __future__ import annotations

import json

import yaml

from io_adapter import IOAdapter, _connected_xinput_slots


def verify_gamepad() -> bool:
    cfg = yaml.safe_load(open("spine/config.yaml", encoding="utf-8"))
    before = _connected_xinput_slots()
    io = IOAdapter(backend="wgc", config=cfg)
    try:
        during = _connected_xinput_slots()
        io.hold_direction("E")
        io.hold_direction("HOLD")
        ok = bool(during - before) or (not before and during)
        print(json.dumps({
            "ok": ok,
            "before": sorted(before),
            "during": sorted(during),
            "recoveries": io._gamepad_recoveries,
        }))
        return ok
    finally:
        io.close()


if __name__ == "__main__":
    raise SystemExit(0 if verify_gamepad() else 1)
