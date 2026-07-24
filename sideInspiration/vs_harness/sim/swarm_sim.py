from __future__ import annotations

import math
from dataclasses import dataclass, field

import cv2
import numpy as np


@dataclass
class SwarmSim:
    """Lightweight top-down swarm used to exercise movers without the game."""

    width: int = 320
    height: int = 240
    seed: int = 0
    n_enemies: int = 40
    n_gems: int = 12
    player_speed: float = 55.0
    enemy_speed: float = 28.0
    contact_radius: float = 8.0
    dt: float = 1.0 / 30.0
    rng: np.random.Generator = field(init=False)
    player: np.ndarray = field(init=False)
    enemies: np.ndarray = field(init=False)
    gems: np.ndarray = field(init=False)
    alive: bool = True
    time_s: float = 0.0
    hits: int = 0
    gems_collected: int = 0
    heading: str = "HOLD"

    def __post_init__(self) -> None:
        self.reset(self.seed)

    def reset(self, seed: int | None = None) -> None:
        if seed is not None:
            self.seed = seed
        self.rng = np.random.default_rng(self.seed)
        self.player = np.array([self.width / 2, self.height / 2], dtype=np.float64)
        angles = self.rng.uniform(0, 2 * math.pi, size=self.n_enemies)
        radii = self.rng.uniform(60, min(self.width, self.height) * 0.45, size=self.n_enemies)
        self.enemies = np.stack(
            [
                self.player[0] + radii * np.cos(angles),
                self.player[1] + radii * np.sin(angles),
            ],
            axis=1,
        )
        self.gems = self.rng.uniform(
            low=[20, 20],
            high=[self.width - 20, self.height - 20],
            size=(self.n_gems, 2),
        )
        self.alive = True
        self.time_s = 0.0
        self.hits = 0
        self.gems_collected = 0
        self.heading = "HOLD"

    def set_heading(self, heading: str) -> None:
        self.heading = heading

    def step(self, heading: str | None = None) -> None:
        if not self.alive:
            return
        if heading is not None:
            self.heading = heading
        from vs_harness.control.headings import heading_to_vec

        vx, vy = heading_to_vec(self.heading)
        self.player += np.array([vx, vy]) * self.player_speed * self.dt
        self.player[0] = float(np.clip(self.player[0], 8, self.width - 8))
        self.player[1] = float(np.clip(self.player[1], 8, self.height - 8))

        # Enemies chase player
        delta = self.player[None, :] - self.enemies
        dist = np.linalg.norm(delta, axis=1, keepdims=True) + 1e-6
        self.enemies += (delta / dist) * self.enemy_speed * self.dt

        # Contact
        d_player = np.linalg.norm(self.enemies - self.player[None, :], axis=1)
        n_hits = int(np.sum(d_player < self.contact_radius))
        if n_hits:
            self.hits += n_hits
            if self.hits >= 12:
                self.alive = False

        # Gems
        if len(self.gems):
            gd = np.linalg.norm(self.gems - self.player[None, :], axis=1)
            keep = gd >= 10.0
            collected = int(np.sum(~keep))
            self.gems_collected += collected
            self.gems = self.gems[keep]

        self.time_s += self.dt

    def ground_truth_masks(self) -> tuple[np.ndarray, np.ndarray, np.ndarray, tuple[float, float]]:
        h, w = self.height, self.width
        threat_u8 = np.zeros((h, w), dtype=np.uint8)
        gems_u8 = np.zeros((h, w), dtype=np.uint8)
        player_u8 = np.zeros((h, w), dtype=np.uint8)
        for x, y in self.enemies:
            cv2.circle(threat_u8, (int(x), int(y)), 5, 1, -1)
        for x, y in self.gems:
            cv2.circle(gems_u8, (int(x), int(y)), 3, 1, -1)
        cv2.circle(player_u8, (int(self.player[0]), int(self.player[1])), 4, 1, -1)
        return (
            threat_u8.astype(bool),
            player_u8.astype(bool),
            gems_u8.astype(bool),
            (float(self.player[0]), float(self.player[1])),
        )

    def render(self) -> np.ndarray:
        frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        frame[:] = (30, 30, 36)
        for x, y in self.enemies:
            cv2.circle(frame, (int(x), int(y)), 5, (40, 40, 220), -1)
        for x, y in self.gems:
            cv2.circle(frame, (int(x), int(y)), 3, (220, 80, 220), -1)
        cv2.circle(frame, (int(self.player[0]), int(self.player[1])), 5, (80, 220, 80), -1)
        return frame
