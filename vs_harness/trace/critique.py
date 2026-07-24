from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from vs_harness.trace.writer import read_trace


def critique_run(path: str | Path) -> dict[str, Any]:
    """Offline critique: summarize failure modes from a trace file."""
    events = read_trace(path)
    start = next((e for e in events if e.get("type") == "run_start"), {})
    end = next((e for e in events if e.get("type") == "run_end"), {})
    ticks = [e for e in events if e.get("type") == "tick"]

    wrapper_modes = Counter(e.get("wrapper_mode") for e in ticks)
    headings = [e.get("heading") for e in ticks]
    entropy = _heading_entropy(headings)
    low_clear = sum(1 for e in ticks if float(e.get("clearance", 99)) < 6.0)

    notes = []
    if end.get("alive") is False:
        notes.append(
            f"Died at t={end.get('survive_s'):.1f}s after {end.get('hits')} hits "
            f"with approach={start.get('approach_id')} wrapper={start.get('wrapper_enabled')}."
        )
    if entropy > 2.5:
        notes.append("High heading entropy — possible indecisive chatter.")
    if wrapper_modes.get("breakout", 0) > len(ticks) * 0.2:
        notes.append("Frequent breakouts — often boxed; check perception dilation / commit_ms.")
    if low_clear > len(ticks) * 0.3:
        notes.append("Long time at low clearance — mover may prefer gems over escape.")

    return {
        "run_id": start.get("run_id"),
        "approach_id": start.get("approach_id"),
        "wrapper_enabled": start.get("wrapper_enabled"),
        "survive_s": end.get("survive_s"),
        "hits": end.get("hits"),
        "gems": end.get("gems"),
        "breakout_count": end.get("breakout_count"),
        "mean_entropy": end.get("mean_entropy", entropy),
        "wrapper_mode_hist": dict(wrapper_modes),
        "notes": notes,
    }


def _heading_entropy(headings: list[str | None], window: int = 16) -> float:
    import math

    if len(headings) < 2:
        return 0.0
    # average per-window Shannon entropy
    ents = []
    for i in range(0, max(1, len(headings) - window)):
        chunk = headings[i : i + window]
        c = Counter(chunk)
        n = sum(c.values())
        ent = -sum((v / n) * math.log((v / n) + 1e-12, 2) for v in c.values())
        ents.append(ent)
    return float(sum(ents) / len(ents)) if ents else 0.0


def critique_path_to_json(path: str | Path, out: str | Path | None = None) -> dict[str, Any]:
    report = critique_run(path)
    if out:
        Path(out).write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report
