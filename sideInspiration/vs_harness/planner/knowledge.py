from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from vs_harness.paths import resolve_config_path


def load_knowledge(path: str | Path) -> dict[str, Any]:
    resolved = resolve_config_path(path)
    with resolved.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def format_knowledge_for_prompt(knowledge: dict[str, Any]) -> str:
    lines = ["Known evolutions:"]
    for evo in knowledge.get("evolutions", []):
        lines.append(
            f"- {evo.get('weapon')} + {evo.get('passive')} -> {evo.get('evolved')}"
        )
    hints = knowledge.get("policy_hints", [])
    if hints:
        lines.append("Policy hints:")
        for h in hints:
            lines.append(f"- {h}")
    return "\n".join(lines)
