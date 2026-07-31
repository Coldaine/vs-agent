from __future__ import annotations

"""Trace schema for VS harness runs.

Episode JSONL event types:
  - run_start: {run_id, approach_id, wrapper_enabled, config_snapshot, seed, mode}
  - tick: {t, screen_mode, heading, keys, wrapper_mode, clearance, trapped,
           intent_mode, perception_ms, heading_entropy, masks_rle?}
  - planner: {t, intent, trigger}
  - levelup: {t, options, choice_index}
  - run_end: {t, alive, survive_s, hits, gems, breakout_count, mean_entropy, death_reason}

Masks stored as RLE via perception.masks.encode_rle when enabled.
"""

from typing import Any, TypedDict


class RunStartEvent(TypedDict, total=False):
    type: str
    run_id: str
    approach_id: str
    wrapper_enabled: bool
    seed: int
    mode: str
    config_snapshot: dict[str, Any]


class TickEvent(TypedDict, total=False):
    type: str
    t: float
    screen_mode: str
    heading: str
    keys: list[str]
    wrapper_mode: str
    clearance: float
    urgency: float
    intent_mode: str
    perception_ms: float
    approach_id: str
    threat_rle: dict[str, Any]
    free_clearance: float


class RunEndEvent(TypedDict, total=False):
    type: str
    t: float
    alive: bool
    survive_s: float
    hits: int
    gems: int
    breakout_count: int
    mean_entropy: float
    death_reason: str

