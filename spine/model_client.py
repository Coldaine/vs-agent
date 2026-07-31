"""Compatibility helpers backed exclusively by the official Codex SDK.

Async callers use the ``acall_*`` surface. Legacy synchronous scripts are
supported only when no event loop is running; each call owns and closes one SDK
client. OAuth credential material remains owned by Codex.
"""

from __future__ import annotations

import asyncio
import glob
import hashlib
import json
import os
import shutil
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Callable, Mapping

from codex_sdk_client import CodexAgentClient


LOG = "model_calls.jsonl"
DIRECTIONS = {"N", "NE", "E", "SE", "S", "SW", "W", "NW", "HOLD"}
FORBIDDEN_API_KEYS = (
    "OPENAI_API_KEY",
    "OPENROUTER_API_KEY",
    "DEEPSEEK_API_KEY",
)
_CLIENT_FACTORY: Callable[[], CodexAgentClient] | None = None


def assert_oauth_only_environment(
    environ: Mapping[str, str] | None = None,
) -> None:
    """Fail closed if an API-backed model path could be selected accidentally."""

    values = os.environ if environ is None else environ
    present = [name for name in FORBIDDEN_API_KEYS if values.get(name)]
    if present:
        raise RuntimeError(
            "ChatGPT Pro OAuth only: remove API-key variables from the "
            f"model process ({', '.join(present)})"
        )


def set_client_factory_for_testing(
    factory: Callable[[], CodexAgentClient] | None,
) -> None:
    global _CLIENT_FACTORY
    _CLIENT_FACTORY = factory


def _new_client() -> CodexAgentClient:
    return (_CLIENT_FACTORY or CodexAgentClient)()


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
            "model": "codex-sdk-configured",
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
            raise RuntimeError("failed to encode frame for Codex SDK attachment")
        yield path


async def _ainvoke(
    fn: str,
    role: str,
    prompt: str,
    schema: dict,
    image_path=None,
) -> dict:
    started = time.monotonic()
    ok = False
    client = None
    try:
        assert_oauth_only_environment()
        client = _new_client()
        await client.start()
        invocation = await client.invoke(
            role, prompt, schema, image_path=image_path
        )
        ok = True
        return invocation.payload
    finally:
        try:
            if client is not None:
                await client.close()
        finally:
            _log(fn, _hash(prompt), (time.monotonic() - started) * 1000.0, ok)


def _run_sync(async_name: str, operation: Callable[[], object]):
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(operation())
    raise RuntimeError(
        f"synchronous model helper cannot run inside an event loop; await {async_name}"
    )


FOLLOWER_SCHEMA = {
    "type": "object",
    "properties": {
        "direction": {"type": "string", "enum": sorted(DIRECTIONS)},
        "speed": {"type": "number", "minimum": 0, "maximum": 1},
        "reason": {"type": "string"},
    },
    "required": ["direction", "speed", "reason"],
    "additionalProperties": False,
}


async def acall_follower(
    prompt_text: str, state: dict, frame, brief: str
) -> tuple[str, float]:
    filled = (
        prompt_text.replace("{{STRATEGY_BRIEF}}", brief or "")
        .replace("{{STATE_JSON}}", json.dumps(state, separators=(",", ":")))
    )
    with _frame_path(frame) as image_path:
        result = await _ainvoke(
            "call_follower", "follower", filled, FOLLOWER_SCHEMA, image_path
        )
    direction = str(result.get("direction", "HOLD")).upper()
    if direction not in DIRECTIONS:
        direction = "HOLD"
    speed = max(0.0, min(1.0, float(result.get("speed", 1.0))))
    return direction, speed


def call_follower(prompt_text: str, state: dict, frame, brief: str) -> tuple[str, float]:
    return _run_sync(
        "acall_follower",
        lambda: acall_follower(prompt_text, state, frame, brief),
    )


FOLLOWER_EVAL_SCHEMA = {
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


async def acall_follower_eval(prompt_text: str, frame_path: str) -> dict:
    prompt = prompt_text + "\nReturn the requested evaluation object."
    return await _ainvoke(
        "call_follower_eval", "follower", prompt, FOLLOWER_EVAL_SCHEMA, Path(frame_path)
    )


def call_follower_eval(prompt_text: str, frame_path: str) -> dict:
    return _run_sync(
        "acall_follower_eval", lambda: acall_follower_eval(prompt_text, frame_path)
    )


LEADER_SCHEMA = {
    "type": "object",
    "properties": {
        "pick": {"type": "integer", "minimum": 1},
        "why": {"type": "string"},
        "brief_update": {"type": "string"},
    },
    "required": ["pick", "why", "brief_update"],
    "additionalProperties": False,
}


async def acall_leader(
    prompt_text: str, frame, options: list[str], brief: str
) -> dict:
    prompt = (
        f"{prompt_text}\n\nCurrent strategy brief:\n{brief}\n\n"
        f"Level-up options, top to bottom: {json.dumps(options)}\n"
        "Pick a one-based option index."
    )
    result = await _ainvoke("call_leader", "leader", prompt, LEADER_SCHEMA)
    return {
        "pick": result.get("pick", 1),
        "why": result.get("why", ""),
        "brief_update": result.get("brief_update", brief),
    }


def call_leader(prompt_text: str, frame, options: list[str], brief: str) -> dict:
    return _run_sync(
        "acall_leader",
        lambda: acall_leader(prompt_text, frame, options, brief),
    )


SUBAGENT_SCHEMA = {
    "type": "object",
    "additionalProperties": True,
}


async def acall_subagent(prompt_text: str, packet: dict, keyframes=None) -> dict:
    prompt = (
        prompt_text
        + "\n\nPACKET:\n"
        + json.dumps(packet, default=str)
        + "\nReturn one valid JSON object and no surrounding prose."
    )
    image_path = Path(keyframes[0]) if keyframes else None
    return await _ainvoke(
        "call_subagent", "leader", prompt, SUBAGENT_SCHEMA, image_path
    )


def call_subagent(prompt_text: str, packet: dict, keyframes=None) -> dict:
    return _run_sync(
        "acall_subagent",
        lambda: acall_subagent(prompt_text, packet, keyframes),
    )


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


async def acall_labeler(frame_path: str, rubric_pointer: str) -> dict:
    return await _ainvoke(
        "call_labeler", "leader", rubric_pointer, LABEL_SCHEMA, Path(frame_path)
    )


def call_labeler(frame_path: str, rubric_pointer: str) -> dict:
    return _run_sync(
        "acall_labeler", lambda: acall_labeler(frame_path, rubric_pointer)
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


async def acall_auditor(
    frame_path: str, rubric_pointer: str, primary: dict
) -> dict:
    prompt = rubric_pointer + "\n\nPRIMARY LABEL TO AUDIT:\n" + json.dumps(primary)
    return await _ainvoke(
        "call_auditor", "leader", prompt, AUDIT_SCHEMA, Path(frame_path)
    )


def call_auditor(frame_path: str, rubric_pointer: str, primary: dict) -> dict:
    return _run_sync(
        "acall_auditor",
        lambda: acall_auditor(frame_path, rubric_pointer, primary),
    )


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
