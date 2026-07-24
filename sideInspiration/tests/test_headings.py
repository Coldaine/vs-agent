from vs_harness.control.headings import angle_delta, heading_to_keys, vec_to_heading


def test_vec_to_heading_cardinals():
    assert vec_to_heading(0, -1) == "N"
    assert vec_to_heading(1, 0) == "E"
    assert vec_to_heading(0, 1) == "S"
    assert vec_to_heading(-1, 0) == "W"
    assert vec_to_heading(0, 0) == "HOLD"


def test_heading_to_keys():
    assert heading_to_keys("NE") == {"w", "d"}
    assert heading_to_keys("HOLD") == set()


def test_angle_delta():
    assert angle_delta("N", "N") == 0
    assert angle_delta("N", "S") == 180
    assert angle_delta("E", "NE") == 45
