from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import numpy as np


class ScreenMode(str, Enum):
    PLAYING = "playing"
    LEVELUP = "levelup"
    CHEST = "chest"
    PAUSE = "pause"
    MAP = "map"
    DEAD = "dead"
    TITLE = "title"
    UNKNOWN = "unknown"


class WrapperMode(str, Enum):
    PASSTHROUGH = "passthrough"
    COMMITTED = "committed"
    BREAKOUT = "breakout"


HEADINGS_8 = ("N", "NE", "E", "SE", "S", "SW", "W", "NW", "HOLD")

# Unit vectors for 8-way headings (x right, y down in image coords)
HEADING_VEC: dict[str, tuple[float, float]] = {
    "N": (0.0, -1.0),
    "NE": (0.7071, -0.7071),
    "E": (1.0, 0.0),
    "SE": (0.7071, 0.7071),
    "S": (0.0, 1.0),
    "SW": (-0.7071, 0.7071),
    "W": (-1.0, 0.0),
    "NW": (-0.7071, -0.7071),
    "HOLD": (0.0, 0.0),
}


@dataclass
class IntentPacket:
    mode: str = "kite"  # farm | kite | boss | gem_vacuum | chest_hunt
    attractors: list[str] = field(default_factory=lambda: ["open_space"])
    orbit: str = "cw"  # cw | ccw | none
    build_plan: list[str] = field(default_factory=list)
    levelup_policy: list[str] = field(default_factory=list)
    spatial_bias: str = ""
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "attractors": list(self.attractors),
            "orbit": self.orbit,
            "build_plan": list(self.build_plan),
            "levelup_policy": list(self.levelup_policy),
            "spatial_bias": self.spatial_bias,
            "notes": self.notes,
        }


@dataclass
class PerceptionFrame:
    timestamp_s: float
    frame_bgr: np.ndarray
    threat_union: np.ndarray  # bool HxW
    player_mask: np.ndarray  # bool HxW
    gem_mask: np.ndarray  # bool HxW
    player_xy: tuple[float, float]
    inference_ms: float
    backend: str
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class MoverProposal:
    heading: str
    urgency: float = 0.5
    trapped: bool = False
    clearance_px: float = 0.0
    debug: dict[str, Any] = field(default_factory=dict)


@dataclass
class ControlCommand:
    heading: str
    keys: set[str]
    wrapper_mode: WrapperMode
    approach_id: str
    urgency: float = 0.5
    debug: dict[str, Any] = field(default_factory=dict)
