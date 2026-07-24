import threading
import time

import numpy as np

import coordinator
import input_health
from controller import Controller
from io_adapter import IOAdapter


class _ProbeIO:
    def __init__(self):
        self.frames = [
            np.zeros((4, 4, 3), dtype=np.uint8),
            np.full((4, 4, 3), 20, dtype=np.uint8),
        ]
        self.keys = []

    def screenshot(self):
        return type("Frame", (), {"image": self.frames.pop(0)})()

    def menu_navigate(self, key):
        self.keys.append(key)


def test_input_health_measures_transition_before_restore():
    io = _ProbeIO()
    assert input_health.probe_health(io, threshold=1.0)
    assert io.keys == ["down", "up"]


def test_stale_pilot_latency_is_not_reported():
    controller = Controller(
        type("IO", (), {"hold_direction": lambda *_args: None})(),
        {"staleness_ms": 1, "collision_radius_px": 50, "escape_vector_k": 1, "dither_ms": 0},
    )
    controller._last_pilot_proposal = (time.monotonic() - 1.0, "E", 1.0)
    controller._last_latency = 900.0
    assert controller._fresh_proposal() == (None, 1.0, None)


def test_pwm_thread_is_joined_before_neutralize():
    class Keys:
        def __init__(self):
            self.events = []

        def keyDown(self, key):
            self.events.append(("down", key))

        def keyUp(self, key):
            self.events.append(("up", key))

    adapter = object.__new__(IOAdapter)
    adapter._input_lock = threading.RLock()
    adapter._pwm_gen = 0
    adapter._pwm_thread = None
    adapter._held = set()
    adapter._input_backend = "keyboard"
    adapter._keys = Keys()
    adapter._gamepad = None

    adapter.hold_direction("E", 0.5)
    time.sleep(0.15)
    adapter.neutralize()

    assert adapter._pwm_thread is None
    assert adapter._held == set()
    assert adapter._keys.events[-1] == ("up", "right")


def test_coordinator_keeps_scanning_after_bad_json():
    assert coordinator._parse_outcome(
        '{"run_id":"valid"}\n{"run_id":'
    ) == {"run_id": "valid"}
