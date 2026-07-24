from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any


class TraceWriter:
    def __init__(self, root: str | Path, run_id: str | None = None):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.run_id = run_id or time.strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:8]
        self.path = self.root / f"{self.run_id}.jsonl"
        self._fh = self.path.open("w", encoding="utf-8")

    def write(self, event: dict[str, Any]) -> None:
        self._fh.write(json.dumps(event, default=_json_default) + "\n")
        self._fh.flush()

    def close(self) -> None:
        self._fh.close()


def _json_default(obj: Any) -> Any:
    if hasattr(obj, "value"):
        return obj.value
    if hasattr(obj, "tolist"):
        return obj.tolist()
    return str(obj)


def read_trace(path: str | Path) -> list[dict[str, Any]]:
    events = []
    with Path(path).open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                events.append(json.loads(line))
    return events
