"""trace.py — episode writer. Spec: docs/trace_spec.md. Append-only."""

from __future__ import annotations
import json, os, time, hashlib


class EpisodeWriter:
    def __init__(self, episodes_dir: str, run_id: str):
        self.dir = os.path.join(episodes_dir, run_id)
        os.makedirs(os.path.join(self.dir, "frames"), exist_ok=True)
        os.makedirs(os.path.join(self.dir, "keyframes"), exist_ok=True)
        self._states = open(os.path.join(self.dir, "states.jsonl"), "a")
        self._planner = open(os.path.join(self.dir, "planner.jsonl"), "a")
        self.t0 = time.monotonic()

    def t(self) -> float:
        return time.monotonic() - self.t0

    def log_tick(self, hp, level, timer, inventory, threats, gems,
                 rule_fired, latency_ms, action, reflex_override):
        self._states.write(json.dumps({
            "t": round(self.t(), 2), "hp": hp, "level": level, "timer": timer,
            "inventory": inventory,
            "threats_by_octant": threats, "gems_by_octant": gems,
            "reflex_override": reflex_override, "rule_fired": rule_fired,
            "pilot_latency_ms": latency_ms, "action": action,
        }) + "\n")
        self._states.flush()

    def log_planner(self, options, pick, why, brief_update):
        self._planner.write(json.dumps({
            "t": round(self.t(), 2), "options": options, "pick": pick,
            "why": why, "brief_update": brief_update}) + "\n")
        self._planner.flush()

    def save_frame(self, image_bytes: bytes, keyframe: bool = False, name: str | None = None):
        sub = "keyframes" if keyframe else "frames"
        name = name or f"{int(self.t()*2):07d}.jpg"
        with open(os.path.join(self.dir, sub, name), "wb") as f:
            f.write(image_bytes)

    def close(self, survived_s, level, kills, invalid, prompt_hashes: dict):
        with open(os.path.join(self.dir, "outcome.json"), "w") as f:
            json.dump({
                "survived_s": survived_s, "level": level, "kills": kills,
                "cause_of_death": None,      # filled by review, not runtime
                "invalid": invalid,
                "prompt_hashes": prompt_hashes}, f, indent=2)
        self._states.close()
        self._planner.close()


def hash_prompt(path: str) -> str:
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()[:12]
