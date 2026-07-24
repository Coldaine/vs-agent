from __future__ import annotations

import logging
import os
import shutil
import subprocess
import time
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class LaunchResult:
    ok: bool
    method: str
    detail: str
    pid: int | None = None


def launch_or_attach(cfg: dict[str, Any]) -> LaunchResult:
    """Best-effort launch / attach for Vampire Survivors.

    Order:
      1. If a window matching host.window_title already exists → attach
      2. Else try host.launch_command or Steam app id
      3. Else report manual-start instructions
    """
    host = cfg.get("host", {})
    title = str(host.get("window_title", "Vampire Survivors"))
    existing = find_window(title)
    if existing is not None:
        focused = focus_window(title)
        return LaunchResult(
            ok=True,
            method="attach",
            detail=f"found window {existing!r}; focus={'ok' if focused else 'skipped'}",
        )

    launch_cmd = host.get("launch_command")
    steam_app_id = host.get("steam_app_id", "1794680")  # Vampire Survivors
    if launch_cmd:
        try:
            proc = subprocess.Popen(launch_cmd, shell=True)
            time.sleep(float(host.get("launch_wait_s", 5.0)))
            focus_window(title)
            return LaunchResult(ok=True, method="launch_command", detail=str(launch_cmd), pid=proc.pid)
        except Exception as exc:  # noqa: BLE001
            return LaunchResult(ok=False, method="launch_command", detail=str(exc))

    steam = shutil.which("steam") or shutil.which("steam.exe")
    if steam and steam_app_id:
        try:
            proc = subprocess.Popen([steam, f"steam://run/{steam_app_id}"])
            return LaunchResult(
                ok=True,
                method="steam",
                detail=f"{steam} steam://run/{steam_app_id}",
                pid=proc.pid,
            )
        except Exception as exc:  # noqa: BLE001
            return LaunchResult(ok=False, method="steam", detail=str(exc))

    return LaunchResult(
        ok=False,
        method="manual",
        detail=(
            f"No running window titled like {title!r} and no Steam/launch_command. "
            "Start Vampire Survivors windowed, then re-run with loop.mode=live."
        ),
    )


def find_window(title_substr: str) -> str | None:
    """Return a matching window title if discoverable on this OS."""
    title_substr_l = title_substr.lower()
    # Linux: wmctrl
    if shutil.which("wmctrl"):
        try:
            out = subprocess.check_output(["wmctrl", "-l"], text=True, timeout=2)
            for line in out.splitlines():
                if title_substr_l in line.lower():
                    return line.strip()
        except Exception:
            pass
    # Optional pygetwindow
    try:
        import pygetwindow as gw  # type: ignore

        for w in gw.getAllTitles():
            if w and title_substr_l in w.lower():
                return w
    except Exception:
        pass
    return None


def focus_window(title_substr: str) -> bool:
    title_substr_l = title_substr.lower()
    if shutil.which("wmctrl"):
        try:
            out = subprocess.check_output(["wmctrl", "-l"], text=True, timeout=2)
            for line in out.splitlines():
                if title_substr_l in line.lower():
                    wid = line.split()[0]
                    subprocess.check_call(["wmctrl", "-ia", wid], timeout=2)
                    return True
        except Exception:
            return False
    try:
        import pygetwindow as gw  # type: ignore

        for w in gw.getWindowsWithTitle(title_substr):
            try:
                w.activate()
                return True
            except Exception:
                continue
    except Exception:
        pass
    return False


def env_endpoint_summary(cfg: dict[str, Any]) -> dict[str, Any]:
    openai = cfg.get("openai", {})
    key_env = openai.get("api_key_env", "VS_OPENAI_API_KEY")
    return {
        "base_url": openai.get("base_url"),
        "leader_model": openai.get("leader_model"),
        "follower_model": openai.get("follower_model"),
        "api_key_set": bool(os.environ.get(key_env)),
        "api_key_env": key_env,
    }
