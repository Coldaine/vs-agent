from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import yaml

from vs_harness.paths import resolve_config_path


_ENV_PATTERN = re.compile(r"\$\{([^}:]+)(?::-([^}]*))?\}")


def _expand_env(value: str) -> str:
    def repl(match: re.Match[str]) -> str:
        key = match.group(1)
        default = match.group(2)
        env = os.environ.get(key)
        if env is not None:
            return env
        return default if default is not None else match.group(0)

    return _ENV_PATTERN.sub(repl, value)


def _expand_tree(node: Any) -> Any:
    if isinstance(node, dict):
        return {k: _expand_tree(v) for k, v in node.items()}
    if isinstance(node, list):
        return [_expand_tree(v) for v in node]
    if isinstance(node, str):
        return _expand_env(node)
    return node


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    out = dict(base)
    for key, val in override.items():
        if key == "inherits":
            continue
        if isinstance(val, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], val)
        else:
            out[key] = val
    return out


def load_config(path: str | Path, _seen: frozenset[Path] | None = None) -> dict[str, Any]:
    path = resolve_config_path(path)
    seen = _seen or frozenset()
    if path in seen:
        cycle = " -> ".join(str(p) for p in (*seen, path))
        raise ValueError(f"Config inheritance cycle: {cycle}")
    seen = seen | {path}

    with path.open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    inherits = raw.get("inherits")
    if inherits:
        parent_path = Path(inherits)
        if not parent_path.is_absolute():
            candidates = [
                Path.cwd() / parent_path,
                path.parent / parent_path,
                path.parent.parent / parent_path,
            ]
            parent_path = next((c for c in candidates if c.exists()), candidates[0])
        parent = load_config(parent_path, _seen=seen)
        merged = _deep_merge(parent, raw)
    else:
        merged = raw

    return _expand_tree(merged)
