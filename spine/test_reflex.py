from reflex import Detection, veto_check, escape_vector


def test_veto_blocks_threat_ahead():
    player = Detection(0, 0, "player")
    enemy = Detection(10, 0, "enemy")          # due east, within radius
    assert veto_check("E", [enemy], player, 20.0) is True


def test_veto_allows_clear_direction():
    player = Detection(0, 0, "player")
    enemy = Detection(10, 0, "enemy")
    assert veto_check("W", [enemy], player, 20.0) is False


def test_veto_hold_is_never_vetoed():
    player = Detection(0, 0, "player")
    enemy = Detection(1, 0, "enemy")
    assert veto_check("HOLD", [enemy], player, 20.0) is False


def test_escape_runs_away_from_enemy():
    player = Detection(0, 0, "player")
    enemy = Detection(10, 0, "enemy")          # east -> escape trends west
    assert escape_vector([enemy], player, 1) in ("W", "NW", "SW")


def test_escape_holds_without_threats():
    player = Detection(0, 0, "player")
    assert escape_vector([], player, 1) == "HOLD"
