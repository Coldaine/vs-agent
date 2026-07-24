from __future__ import annotations

from pathlib import Path


# sideInspiration/ (parent of the vs_harness package)
PACKAGE_ROOT = Path(__file__).resolve().parent.parent


def resolve_config_path(path: str | Path) -> Path:
    """Resolve a config path relative to cwd, then sideInspiration/."""
    p = Path(path)
    if p.is_file():
        return p.resolve()
    candidates = [
        Path.cwd() / p,
        PACKAGE_ROOT / p,
        PACKAGE_ROOT / "configs" / p.name,
    ]
    for c in candidates:
        if c.is_file():
            return c.resolve()
    return (Path.cwd() / p).resolve()


def default_config(name: str = "default.yaml") -> str:
    return str(PACKAGE_ROOT / "configs" / name)
