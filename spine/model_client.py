"""model_client.py — the ONLY file that calls model endpoints.

Credentials are injected into the process (normally with ``doppler run``),
never read from a project-specific Doppler scope or committed ``.env`` file:
  DEEPSEEK_API_KEY    — direct DeepSeek V4 Flash text/reasoning calls
  OPENROUTER_API_KEY  — OpenRouter's free vision router

The follower and frame-labeling calls use OpenRouter's ``openrouter/free``
model because they require image input. The leader and review calls use the
direct DeepSeek API because they are text-only roles.
"""

from __future__ import annotations
import base64
import glob
import hashlib
import json
import os
import re
import shutil
import time

LOG = "model_calls.jsonl"

DIRECTIONS = {"N", "NE", "E", "SE", "S", "SW", "W", "NW", "HOLD"}

# ---------------------------------------------------------------------------
# endpoint / client resolution
# ---------------------------------------------------------------------------
_CLIENTS: dict[str, object] = {}

_DIRECT_DEEPSEEK = {
    "url": "https://api.deepseek.com",
    "key_name": "DEEPSEEK_API_KEY",
    "model": "deepseek-v4-flash",
}
_FREE_OPENROUTER_VISION = {
    "url": "https://openrouter.ai/api/v1",
    "key_name": "OPENROUTER_API_KEY",
    "model": "openrouter/free",
}


def _endpoint(role: str) -> tuple[str, str, str]:
    """Return the fixed provider endpoint and injected credential for a role."""
    role = role.upper()
    provider = (_FREE_OPENROUTER_VISION
                if role in {"FOLLOWER", "LABELER"}
                else _DIRECT_DEEPSEEK)
    key = os.environ.get(provider["key_name"])
    if not key:
        raise RuntimeError(
            f"{provider['key_name']} is not injected — launch via Doppler with "
            "the provider key available in the child process.")
    model = os.environ.get(f"{role}_MODEL", provider["model"])
    return provider["url"], key, model


def _client(role: str):
    from openai import OpenAI  # lazy so import/config errors surface at call time
    url, key, model = _endpoint(role)
    cached = _CLIENTS.get(role)
    if cached is None:
        cached = OpenAI(base_url=url, api_key=key)
        _CLIENTS[role] = cached
    return cached, model


def _log(fn: str, prompt_hash: str, latency_ms: float, ok: bool):
    with open(LOG, "a") as f:
        f.write(json.dumps({"fn": fn, "prompt_hash": prompt_hash,
                            "latency_ms": round(latency_ms, 1),
                            "ok": ok, "t": time.time()}) + "\n")


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:12]


# ---------------------------------------------------------------------------
# image encoding + JSON parsing helpers
# ---------------------------------------------------------------------------
def _encode_frame(frame) -> str:
    """base64 data URL for a Frame (with .image BGR ndarray), a raw
    ndarray, or a path string."""
    if isinstance(frame, str):
        with open(frame, "rb") as f:
            raw = f.read()
        return "data:image/jpeg;base64," + base64.b64encode(raw).decode()
    image = getattr(frame, "image", frame)
    import cv2  # lazy: runtime perception dependency
    ok, buf = cv2.imencode(".jpg", image)
    if not ok:
        raise RuntimeError("failed to JPEG-encode frame for model call")
    return "data:image/jpeg;base64," + base64.b64encode(buf.tobytes()).decode()


def _image_content(frame) -> dict:
    return {"type": "image_url", "image_url": {"url": _encode_frame(frame)}}


def _parse_json(text: str) -> dict:
    """Extract the first JSON object from a response (tolerates ```json
    fences and leading prose)."""
    text = (text or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*", "", text).strip().rstrip("`").strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if m:
            return json.loads(m.group(0))
        raise


def _chat(role: str, messages: list, fn: str, prompt_hash: str,
           max_tokens: int = 512, temperature: float = 0.0) -> str:
    client, model = _client(role)
    t0 = time.monotonic()
    ok = False
    try:
        request = {"model": model, "messages": messages, "max_tokens": max_tokens}
        if role.upper() in {"LEADER", "REVIEWER"}:
            request["reasoning_effort"] = os.environ.get(
                "DEEPSEEK_REASONING_EFFORT", "max")
            request["extra_body"] = {"thinking": {"type": "enabled"}}
        else:
            request["temperature"] = temperature
        resp = client.chat.completions.create(**request)
        content = resp.choices[0].message.content or ""
        ok = True
        return content
    finally:
        _log(fn, prompt_hash, (time.monotonic() - t0) * 1000, ok)


# ---------------------------------------------------------------------------
# runtime calls
# ---------------------------------------------------------------------------
def call_follower(prompt_text: str, state: dict, frame, brief: str) -> str:
    """Returns one of: N NE E SE S SW W NW HOLD. Single token.
    prompt_text contains {{STRATEGY_BRIEF}} and {{STATE_JSON}} slots."""
    filled = (prompt_text
              .replace("{{STRATEGY_BRIEF}}", brief or "")
              .replace("{{STATE_JSON}}",
                       json.dumps(state, separators=(",", ":"))))
    messages = [{"role": "user", "content": [
        {"type": "text", "text": filled},
        _image_content(frame)]}]
    content = _chat("FOLLOWER", messages, "call_follower", _hash(filled),
                    max_tokens=8)
    token = content.strip().upper().split()[0] if content.strip() else "HOLD"
    return re.sub(r"[^A-Z]", "", token)  # controller validates + logs vocab


def call_follower_eval(prompt_text: str, frame_path: str) -> dict:
    """Loop P variant: returns {"action": ..., "threat_octant": ...,
    "gem_octant": ..., "is_level_up": ...} for scoring."""
    suffix = ("\n\nFor evaluation, reply ONLY with JSON: "
              '{"action": "<N|NE|E|SE|S|SW|W|NW|HOLD>", '
              '"threat_octant": "<octant>", "gem_octant": "<octant>", '
              '"is_level_up": <true|false>}')
    filled = (prompt_text
              .replace("{{STRATEGY_BRIEF}}", "")
              .replace("{{STATE_JSON}}", "(offline eval — image only)")) + suffix
    messages = [{"role": "user", "content": [
        {"type": "text", "text": filled},
        _image_content(frame_path)]}]
    content = _chat("FOLLOWER", messages, "call_follower_eval",
                    _hash(filled), max_tokens=128)
    try:
        out = _parse_json(content)
    except Exception:
        tok = re.sub(r"[^A-Z]", "", content.strip().upper().split()[0]) \
            if content.strip() else "HOLD"
        out = {"action": tok}
    out.setdefault("action", "HOLD")
    out["action"] = str(out["action"]).upper()
    return out


def call_leader(prompt_text: str, frame, options: list[str], brief: str) -> dict:
    """Returns {"pick": str, "why": str, "brief_update": str}."""
    user = (f"Current strategy brief:\n{brief}\n\n"
            f"Level-up options (top to bottom): {json.dumps(options)}\n"
            "Reply in JSON only as specified.")
    # DeepSeek V4 Flash is deliberately used as a text-only strategic model.
    # OCR has already supplied the level-up options, so a frame is unnecessary.
    messages = [{"role": "user", "content": prompt_text + "\n\n" + user}]
    content = _chat("LEADER", messages, "call_leader",
                    _hash(prompt_text + user), max_tokens=400)
    out = _parse_json(content)
    return {"pick": out.get("pick", options[0] if options else ""),
            "why": out.get("why", ""),
            "brief_update": out.get("brief_update", brief)}


def call_subagent(prompt_text: str, packet: dict, keyframes=None) -> dict:
    """Fresh-context sub-agent call. Returns parsed JSON. Must retry
    once with 'return valid JSON only' if parsing fails, then raise."""
    payload = prompt_text + "\n\nPACKET:\n" + json.dumps(packet, default=str)
    # Reviewers use direct DeepSeek text reasoning. Frame observations are
    # captured in the packet rather than sending unsupported image content.
    messages = [{"role": "user", "content": payload}]
    phash = _hash(payload)
    content = _chat("REVIEWER", messages, "call_subagent", phash,
                    max_tokens=1500)
    try:
        return _parse_json(content)
    except Exception:
        messages.append({"role": "assistant", "content": content})
        messages.append({"role": "user", "content": "Return valid JSON only."})
        content = _chat("REVIEWER", messages, "call_subagent", phash,
                        max_tokens=1500)
        return _parse_json(content)


def call_labeler(frame_path: str, rubric_pointer: str) -> dict:
    messages = [{"role": "user", "content": [
        {"type": "text", "text": rubric_pointer},
        _image_content(frame_path)]}]
    content = _chat("LABELER", messages, "call_labeler",
                    _hash(rubric_pointer + frame_path), max_tokens=400)
    return _parse_json(content)


def call_auditor(frame_path: str, rubric_pointer: str, primary: dict) -> dict:
    """Second-opinion pass. Returns {"agrees": bool, "corrections": ...}."""
    user = (rubric_pointer + "\n\nPRIMARY LABEL TO AUDIT:\n"
            + json.dumps(primary))
    messages = [{"role": "user", "content": [
        {"type": "text", "text": user},
        _image_content(frame_path)]}]
    content = _chat("LABELER", messages, "call_auditor",
                    _hash(user), max_tokens=400)
    out = _parse_json(content)
    out.setdefault("agrees", True)
    return out


def export_gallery_frames(run_dir: str, error: dict, out_dir: str):
    """Copy the failure-window frames + correct-action labels from an
    autopsy follower_error into the gallery (trace_spec.md)."""
    os.makedirs(out_dir, exist_ok=True)
    labels_path = os.path.join(out_dir, "labels.json")
    labels = json.load(open(labels_path)) if os.path.exists(labels_path) else []

    frames = error.get("frames")
    if not frames:
        t = error.get("t") or error.get("irreversible_at_s")
        if t is not None:
            idx = int(float(t) * 2)  # 2fps naming (trace_spec)
            frames = sorted(
                glob.glob(os.path.join(run_dir, "frames", f"{idx:07d}.jpg")))
    for src in (frames or []):
        src_path = src if os.path.exists(src) \
            else os.path.join(run_dir, "frames", os.path.basename(src))
        if not os.path.exists(src_path):
            continue
        base = f"{os.path.basename(run_dir)}_{os.path.basename(src_path)}"
        dst = os.path.join(out_dir, base)
        shutil.copyfile(src_path, dst)
        labels.append({
            "frame": dst,
            "correct_action": error.get("correct_action"),
            "threat_octant": error.get("threat_octant")
            or error.get("threat_vector_at_t"),
            "gem_octant": error.get("gem_octant"),
            "is_level_up": False,
            "source_run": run_dir,
        })
    json.dump(labels, open(labels_path, "w"), indent=2)
