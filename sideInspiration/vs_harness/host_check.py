from __future__ import annotations

import argparse
import platform
import sys
from pathlib import Path

from vs_harness.config import load_config
from vs_harness.host.launch import env_endpoint_summary, find_window, launch_or_attach


def _gpu_summary() -> str:
    import shutil
    import subprocess

    if shutil.which("nvidia-smi"):
        try:
            out = subprocess.check_output(
                [
                    "nvidia-smi",
                    "--query-gpu=name,memory.total,driver_version",
                    "--format=csv,noheader",
                ],
                text=True,
                timeout=5,
            ).strip()
            return out or "nvidia-smi returned empty"
        except Exception as exc:  # noqa: BLE001
            return f"nvidia-smi failed: {exc}"
    return "no nvidia-smi (CPU-only or drivers missing)"


def run_check(config_path: str) -> int:
    cfg = load_config(config_path)
    host = cfg.get("host", {})
    endpoints = env_endpoint_summary(cfg)
    title = host.get("window_title", "Vampire Survivors")

    print("=== VS Harness host check ===")
    print(f"platform: {platform.platform()}")
    print(f"python:   {sys.version.split()[0]}")
    print(f"gpu:      {_gpu_summary()}")
    print(f"window:   title substring = {title!r}")
    print(f"windowed: prefer_windowed = {host.get('prefer_windowed')}")
    print(f"capture:  backend = {host.get('capture_backend')}")
    print(f"steam:    app_id = {host.get('steam_app_id')}")
    print(f"kill:     {host.get('kill_switch_key')}")
    print(f"openai:   base_url = {endpoints['base_url']}")
    print(f"openai:   leader_model = {endpoints['leader_model']}")
    print(f"openai:   follower_model = {endpoints['follower_model']}")
    print(f"openai:   api_key_env = {endpoints['api_key_env']} set={endpoints['api_key_set']}")

    found = find_window(str(title))
    print(f"window_scan: {'FOUND ' + found if found else 'not found (ok for sim)'}")

    print("\nHost assumptions for live play:")
    print("  1. RTX 5090 (or similar) machine with Vampire Survivors via Steam")
    print("  2. Game in windowed / borderless windowed (not exclusive fullscreen)")
    print("  3. VS_OPENAI_BASE_URL + VS_OPENAI_API_KEY for leader/follower (OpenAI-compatible)")
    print("  4. Optional: sam3/ultralytics/torch for perception backends")
    print("  5. Classic plan path: configs/vlm_follower.yaml (follower_hz=2)")
    print("  6. Kill switch: press F8 during live runs")

    dry = launch_or_attach({**cfg, "host": {**host, "launch_command": None, "steam_app_id": None}})
    print(f"\nattach_probe: method={dry.method} ok={dry.ok} detail={dry.detail}")

    ok = True
    if host.get("prefer_windowed") is not True:
        print("WARN: prefer_windowed is not true")
    if not endpoints.get("base_url"):
        print("ERROR: openai.base_url missing")
        ok = False
    if not endpoints.get("api_key_set"):
        print(f"WARN: {endpoints['api_key_env']} unset — leader/fast_vlm live calls will fail (sim still works)")

    print("\nRESULT:", "OK" if ok else "FAILED")
    return 0 if ok else 1


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Check VS harness host/endpoint config")
    parser.add_argument(
        "--config",
        default="configs/default.yaml",
        type=Path,
        help="Path to YAML config",
    )
    args = parser.parse_args(argv)
    raise SystemExit(run_check(str(args.config)))


if __name__ == "__main__":
    main()
