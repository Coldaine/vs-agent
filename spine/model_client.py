"""Compatibility model helpers backed exclusively by ChatGPT Pro OAuth.

There is no API client in this module. All model work is delegated to the
locally authenticated Codex CLI through :mod:`oauth_codex`; both compatibility
roles currently resolve to ``gpt-5.6-luna``. OAuth credential material remains
owned by Codex and is never read by this repository.
"""

from __future__ import annotations

import glob
import hashlib
import json
import os
import shutil
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path

from oauth_codex import CodexOAuthRunner, assert_oauth_only_environment


LOG = "model_calls.jsonl"
DIRECTIONS = {"N", "NE", "E", "SE", "S", "SW", "W", "NW", "HOLD"}
_RUNNER = None


def set_runner_for_testing(runner) -> None:
    global _RUNNER
    _RUNNER = runner


def _runner():
    global _RUNNER
    assert_oauth_only_environment()
    if _RUNNER is None:
        _RUNNER = CodexOAuthRunner()
    return _RUNNER


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:12]


def _log(fn: str, prompt_hash: str, latency_ms: float, ok: bool) -> None:
    with open(LOG, "a", encoding="utf-8") as stream:
        stream.write(json.dumps({
            "fn": fn,
            "prompt_hash": prompt_hash,
            "latency_ms": round(latency_ms, 1),
            "ok": ok,
            "authentication": "chatgpt-oauth",
            "model": "gpt-5.6-luna",
            "t": time.time(),
        }) + "\n")


@contextmanager
def _frame_path(frame):
    if frame is None:
        yield None
        return
    if isinstance(frame, (str, os.PathLike)):
        yield Path(frame)
        return
    image = getattr(frame, "image", frame)
    import cv2
    with tempfile.TemporaryDirectory(prefix="vs-agent-frame-") as temp_name:
        path = Path(temp_name, "frame.jpg")
        if not cv2.imwrite(str(path), image):
            raise RuntimeError("failed to encode frame for Codex OAuth attachment")
        yield path


def _invoke(fn: str, role: str, prompt: str, schema: dict | None, image_path=None) -> dict:
    started = time.monotonic()
    ok = False
    try:
        result = _runner().invoke(role, prompt, schema, image_path=image_path)
        ok = True
        return result
    finally:
        _log(fn, _hash(prompt), (time.monotonic() - started) * 1000.0, ok)


PILOT_SCHEMA = {
    "type": "object",
    "properties": {
        "direction": {"type": "string", "enum": sorted(DIRECTIONS)},
        "speed": {"type": "number", "minimum": 0, "maximum": 1},
        "reason": {"type": "string"},
    },
    "required": ["direction", "speed", "reason"],
    "additionalProperties": False,
}


def call_pilot(prompt_text: str, state: dict, frame, brief: str) -> tuple[str, float]:
    filled = (
        prompt_text.replace("{{STRATEGY_BRIEF}}", brief or "")
        .replace("{{STATE_JSON}}", json.dumps(state, separators=(",", ":")))
    )
    with _frame_path(frame) as image_path:
        result = _invoke("call_pilot", "follower", filled, PILOT_SCHEMA, image_path)
    direction = str(result.get("direction", "HOLD")).upper()
    if direction not in DIRECTIONS:
        direction = "HOLD"
    speed = max(0.0, min(1.0, float(result.get("speed", 1.0))))
    return direction, speed


PILOT_EVAL_SCHEMA = {
    "type": "object",
    "properties": {
        "action": {"type": "string", "enum": sorted(DIRECTIONS)},
        "threat_octant": {"type": "string"},
        "gem_octant": {"type": "string"},
        "is_level_up": {"type": "boolean"},
    },
    "required": ["action", "threat_octant", "gem_octant", "is_level_up"],
    "additionalProperties": False,
}


def call_pilot_eval(prompt_text: str, frame_path: str) -> dict:
    prompt = prompt_text + "\nReturn the requested evaluation object."
    return _invoke(
        "call_pilot_eval", "follower", prompt, PILOT_EVAL_SCHEMA, Path(frame_path)
    )


PLANNER_SCHEMA = {
    "type": "object",
    "properties": {
        "pick": {"type": "integer", "minimum": 1},
        "why": {"type": "string"},
        "brief_update": {"type": "string"},
    },
    "required": ["pick", "why", "brief_update"],
    "additionalProperties": False,
}


def call_planner(prompt_text: str, frame, options: list[str], brief: str) -> dict:
    prompt = (
        f"{prompt_text}\n\nCurrent strategy brief:\n{brief}\n\n"
        f"Level-up options, top to bottom: {json.dumps(options)}\n"
        "Pick a one-based option index."
    )
    result = _invoke("call_planner", "leader", prompt, PLANNER_SCHEMA)
    return {
        "pick": result.get("pick", 1),
        "why": result.get("why", ""),
        "brief_update": result.get("brief_update", brief),
    }


def call_subagent(prompt_text: str, packet: dict, keyframes=None) -> dict:
    prompt = (
        prompt_text
        + "\n\nPACKET:\n"
        + json.dumps(packet, default=str)
        + "\nReturn one valid JSON object and no surrounding prose."
    )
    image_path = Path(keyframes[0]) if keyframes else None
    return _invoke("call_subagent", "leader", prompt, None, image_path)


LABEL_SCHEMA = {
    "type": "object",
    "properties": {
        "threat_octant": {"type": "string"},
        "gem_octant": {"type": "string"},
        "is_level_up": {"type": "boolean"},
        "correct_action": {"type": "string", "enum": sorted(DIRECTIONS)},
    },
    "required": ["threat_octant", "gem_octant", "is_level_up", "correct_action"],
    "additionalProperties": False,
}


def call_labeler(frame_path: str, rubric_pointer: str) -> dict:
    return _invoke(
        "call_labeler", "leader", rubric_pointer, LABEL_SCHEMA, Path(frame_path)
    )


AUDIT_SCHEMA = {
    "type": "object",
    "properties": {
        "agrees": {"type": "boolean"},
        "corrections": {"type": "string"},
    },
    "required": ["agrees", "corrections"],
    "additionalProperties": False,
}


def call_auditor(frame_path: str, rubric_pointer: str, primary: dict) -> dict:
    prompt = rubric_pointer + "\n\nPRIMARY LABEL TO AUDIT:\n" + json.dumps(primary)
    return _invoke("call_auditor", "leader", prompt, AUDIT_SCHEMA, Path(frame_path))


def export_gallery_frames(run_dir: str, error: dict, out_dir: str) -> None:
    os.makedirs(out_dir, exist_ok=True)
    labels_path = os.path.join(out_dir, "labels.json")
    labels = json.load(open(labels_path)) if os.path.exists(labels_path) else []
    frames = error.get("frames")
    if not frames:
        at = error.get("t") or error.get("irreversible_at_s")
        if at is not None:
            index = int(float(at) * 2)
            frames = sorted(glob.glob(os.path.join(run_dir, "frames", f"{index:07d}.jpg")))
    for source in frames or []:
        source_path = source if os.path.exists(source) else os.path.join(
            run_dir, "frames", os.path.basename(source)
        )
        if not os.path.exists(source_path):
            continue
        base = f"{os.path.basename(run_dir)}_{os.path.basename(source_path)}"
        destination = os.path.join(out_dir, base)
        shutil.copyfile(source_path, destination)
        labels.append({
            "frame": destination,
            "correct_action": error.get("correct_action"),
            "threat_octant": error.get("threat_octant") or error.get("threat_vector_at_t"),
            "gem_octant": error.get("gem_octant"),
            "is_level_up": False,
            "source_run": run_dir,
        })
    with open(labels_path, "w", encoding="utf-8") as stream:
        json.dump(labels, stream, indent=2)
