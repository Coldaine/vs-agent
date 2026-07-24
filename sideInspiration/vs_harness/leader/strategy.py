from __future__ import annotations

import json
import os
import time
from typing import Any

import numpy as np

from vs_harness.planner.knowledge import format_knowledge_for_prompt, load_knowledge
from vs_harness.types import IntentPacket, ScreenMode


class StrategyLeader:
    """Event-driven strategy planner (OpenAI-compatible) + offline heuristics."""

    def __init__(self, cfg: dict[str, Any]):
        self.cfg = cfg
        planner = cfg.get("planner", {})
        openai = cfg.get("openai", {})
        self.enabled = bool(planner.get("enabled", True))
        self.refresh_s = float(planner.get("intent_refresh_s", 15.0))
        self.base_url = str(openai.get("base_url", "https://api.openai.com/v1")).rstrip("/")
        self.model = str(openai.get("leader_model", "gpt-4o"))
        key_env = openai.get("api_key_env", "VS_OPENAI_API_KEY")
        self.api_key = os.environ.get(key_env)
        self.timeout_s = float(openai.get("timeout_s", 30.0))
        self.knowledge = load_knowledge(planner.get("knowledge_pack", "configs/evolution_knowledge.yaml"))
        self.intent = IntentPacket(
            mode="kite",
            attractors=["open_space"],
            orbit="cw",
            build_plan=["evolve core weapons"],
            levelup_policy=list(self.knowledge.get("policy_hints", [])[:4]),
        )
        self._last_refresh = 0.0

    def maybe_refresh(self, mode: ScreenMode, frame_bgr: np.ndarray | None, now_s: float) -> IntentPacket:
        if not self.enabled:
            return self.intent
        if mode in (ScreenMode.LEVELUP, ScreenMode.CHEST):
            self.intent = self._decide_paused(mode, frame_bgr)
            self._last_refresh = now_s
            return self.intent
        if now_s - self._last_refresh >= self.refresh_s:
            self.intent = self._refresh_playing()
            self._last_refresh = now_s
        return self.intent

    def choose_levelup_option(self, options: list[str]) -> int:
        """Rank offered options using knowledge pack (offline)."""
        text = " ".join(options).lower()
        best_i, best_score = 0, -1
        for i, opt in enumerate(options):
            score = 0
            ol = opt.lower()
            for evo in self.knowledge.get("evolutions", []):
                if evo.get("weapon", "").lower() in ol or evo.get("passive", "").lower() in ol:
                    score += 3
                if evo.get("evolved", "").lower() in ol:
                    score += 5
            for kw in ("amount", "cooldown", "growth", "might"):
                if kw in ol:
                    score += 2
            if score > best_score:
                best_score = score
                best_i = i
        return best_i

    def _refresh_playing(self) -> IntentPacket:
        if self.api_key:
            try:
                return self._llm_intent(
                    "Gameplay is unpaused. Return an intent JSON with keys "
                    "mode, attractors, orbit, build_plan, levelup_policy, spatial_bias, notes. "
                    "mode one of farm|kite|boss|gem_vacuum|chest_hunt."
                )
            except Exception:
                pass
        # Heuristic default cadence: alternate kite/farm
        mode = "farm" if int(time.time()) % 2 == 0 else "kite"
        return IntentPacket(
            mode=mode,
            attractors=["gems", "open_space"] if mode == "farm" else ["open_space"],
            orbit="cw",
            build_plan=self.intent.build_plan,
            levelup_policy=self.intent.levelup_policy,
            notes="heuristic refresh",
        )

    def _decide_paused(self, mode: ScreenMode, frame_bgr: np.ndarray | None) -> IntentPacket:
        intent = IntentPacket(
            mode="kite",
            attractors=["open_space"],
            orbit=self.intent.orbit,
            build_plan=self.intent.build_plan,
            levelup_policy=self.intent.levelup_policy,
            notes=f"paused:{mode.value}",
        )
        if self.api_key:
            try:
                return self._llm_intent(
                    f"UI mode is {mode.value}. Choose build intent JSON. "
                    f"Knowledge:\n{format_knowledge_for_prompt(self.knowledge)}"
                )
            except Exception:
                return intent
        return intent

    def _llm_intent(self, user_text: str) -> IntentPacket:
        import httpx

        payload = {
            "model": self.model,
            "temperature": 0.2,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are the strategy planner for a Vampire Survivors agent. "
                        "Reply ONLY with compact JSON intent."
                    ),
                },
                {"role": "user", "content": user_text},
            ],
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        with httpx.Client(timeout=self.timeout_s) as client:
            resp = client.post(f"{self.base_url}/chat/completions", headers=headers, json=payload)
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"].strip()
        if content.startswith("```"):
            content = content.strip("`")
            if content.startswith("json"):
                content = content[4:].strip()
        data = json.loads(content)
        return IntentPacket(
            mode=str(data.get("mode", "kite")),
            attractors=list(data.get("attractors", ["open_space"])),
            orbit=str(data.get("orbit", "cw")),
            build_plan=list(data.get("build_plan", [])),
            levelup_policy=list(data.get("levelup_policy", [])),
            spatial_bias=str(data.get("spatial_bias", "")),
            notes=str(data.get("notes", "")),
        )

