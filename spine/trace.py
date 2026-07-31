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
        self._closed = False

    def t(self) -> float:
        return time.monotonic() - self.t0

    def log_tick(self, hp, level, timer, inventory, threats, gems,
                 rule_fired, latency_ms, action, reflex_override):
        self._states.write(json.dumps({
            "t": round(self.t(), 2), "hp": hp, "level": level, "timer": timer,
            "inventory": inventory,
            "threats_by_octant": threats, "gems_by_octant": gems,
            "reflex_override": reflex_override, "rule_fired": rule_fired,
            "follower_latency_ms": latency_ms, "action": action,
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
        if self._closed:
            return
        self._write_outcome(survived_s, level, kills, invalid, prompt_hashes)
        self._close_streams()

    def abort(self, reason: str) -> None:
        """Close an interrupted run while preserving an invalid terminal record."""
        if self._closed:
            return
        self._write_outcome(
            survived_s=round(self.t(), 1),
            level=None,
            kills=None,
            invalid=True,
            prompt_hashes={},
            abort_reason=str(reason),
        )
        self._close_streams()

    def _write_outcome(
        self,
        survived_s,
        level,
        kills,
        invalid,
        prompt_hashes: dict,
        abort_reason: str | None = None,
    ) -> None:
        with open(os.path.join(self.dir, "outcome.json"), "w") as f:
            outcome = {
                "survived_s": survived_s, "level": level, "kills": kills,
                "cause_of_death": None,      # filled by review, not runtime
                "invalid": invalid,
                "prompt_hashes": prompt_hashes,
            }
            if abort_reason is not None:
                outcome["abort_reason"] = abort_reason
            json.dump(outcome, f, indent=2)

    def _close_streams(self) -> None:
        self._states.close()
        self._planner.close()
        self._closed = True


def hash_prompt(path: str) -> str:
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()[:12]
