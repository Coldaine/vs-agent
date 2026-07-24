import numpy as np

from vs_harness.control.commit_breakout import CommitBreakoutWrapper
from vs_harness.types import MoverProposal, PerceptionFrame, WrapperMode


def _perc(clear_center: bool = True) -> PerceptionFrame:
    h, w = 80, 80
    threat = np.zeros((h, w), dtype=bool)
    if not clear_center:
        threat[:] = True
        threat[35:45, 35:45] = False  # tiny pocket
        # surround heavily
        threat[30:50, 30:50] = True
        threat[38:42, 38:42] = False
    player = np.zeros((h, w), dtype=bool)
    player[40, 40] = True
    gems = np.zeros((h, w), dtype=bool)
    return PerceptionFrame(
        timestamp_s=0.0,
        frame_bgr=np.zeros((h, w, 3), dtype=np.uint8),
        threat_union=threat,
        player_mask=player,
        gem_mask=gems,
        player_xy=(40.0, 40.0),
        inference_ms=0.0,
        backend="test",
    )


def test_wrapper_passthrough_when_disabled():
    w = CommitBreakoutWrapper(enabled=False, approach_id="t")
    prop = MoverProposal(heading="E", clearance_px=20)
    cmd = w.apply(prop, _perc(), now_s=0.0)
    assert cmd.wrapper_mode == WrapperMode.PASSTHROUGH
    assert cmd.heading == "E"


def test_wrapper_commits_heading():
    w = CommitBreakoutWrapper(enabled=True, commit_ms=500, approach_id="t", clearance_trap_px=1.0)
    prop = MoverProposal(heading="N", clearance_px=20, trapped=False)
    cmd1 = w.apply(prop, _perc(), now_s=0.0)
    prop2 = MoverProposal(heading="S", clearance_px=20, trapped=False)
    cmd2 = w.apply(prop2, _perc(), now_s=0.1)
    assert cmd1.heading == "N"
    assert cmd2.heading == "N"
    assert cmd2.wrapper_mode == WrapperMode.COMMITTED


def test_wrapper_breakout_when_trapped():
    w = CommitBreakoutWrapper(enabled=True, clearance_trap_px=50.0, approach_id="t")
    prop = MoverProposal(heading="HOLD", clearance_px=0.5, trapped=True)
    cmd = w.apply(prop, _perc(clear_center=False), now_s=0.0)
    assert cmd.wrapper_mode == WrapperMode.BREAKOUT
    assert cmd.heading != "HOLD"
