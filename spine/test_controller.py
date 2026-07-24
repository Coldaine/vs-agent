import pytest

from controller import Controller
from reflex import Detection


class MockIO:
    def __init__(self):
        self.commands = []

    def hold_direction(self, direction, speed=1.0):
        self.commands.append((direction, speed))

    def neutralize(self):
        self.commands.append(("NEUTRAL", 0.0))


def _cfg():
    return {"collision_radius_px": 50, "escape_vector_k": 1,
            "staleness_ms": 800, "dither_ms": 300}


def test_level_up_holds():
    ctrl = Controller(MockIO(), _cfg())
    res = ctrl.tick([], Detection(0, 0, "player"), "LEVEL_UP")
    assert res.action == "HOLD"
    assert res.rule_fired == "level_up"


def test_no_proposal_is_stale():
    ctrl = Controller(MockIO(), _cfg())
    res = ctrl.tick([], Detection(0, 0, "player"), "IN_GAME")
    assert res.rule_fired == "stale"


def test_clean_proposal_commits():
    io = MockIO()
    ctrl = Controller(io, _cfg())
    assert ctrl.submit_pilot_proposal("E", 100.0, 0.5) is True
    res = ctrl.tick([], Detection(0, 0, "player"), "IN_GAME")
    assert res.action == "E"
    assert res.speed == 0.5
    assert res.rule_fired == "clean"
    assert io.commands[-1] == ("E", 0.5)


def test_veto_overrides_into_threat():
    ctrl = Controller(MockIO(), _cfg())
    player = Detection(0, 0, "player")
    enemy = Detection(10, 0, "enemy")          # due east, within collision radius
    ctrl.submit_pilot_proposal("E", 100.0, 1.0)
    res = ctrl.tick([enemy], player, "IN_GAME")
    assert res.rule_fired == "veto"
    assert res.action != "E"


def test_invalid_proposal_rejected():
    ctrl = Controller(MockIO(), _cfg())
    assert ctrl.submit_pilot_proposal("NORTH", 100.0) is False
