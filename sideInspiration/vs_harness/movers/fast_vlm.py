from __future__ import annotations

import base64
import json
import time
from typing import Any

import cv2
import numpy as np

from vs_harness.control.headings import valid_heading
from vs_harness.movers.base import Mover
from vs_harness.movers.sector_density import SectorDensityMover
from vs_harness.perception.masks import dilate_bool, distance_to_threat
from vs_harness.types import IntentPacket, MoverProposal, PerceptionFrame


class FastVLMMover(Mover):
    """OpenAI-compatible VLM mover (~2 Hz). Falls back to sector_density offline."""

    approach_id = "fast_vlm"

    def __init__(
        self,
        base_url: str,
        api_key: str | None,
        model: str,
        timeout_s: float = 30.0,
        min_interval_s: float = 0.5,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout_s = timeout_s
        self.min_interval_s = min_interval_s
        self._last_t = 0.0
        self._last_heading = "HOLD"
        self._fallback = SectorDensityMover()

    def propose(
        self,
        perception: PerceptionFrame,
        intent: IntentPacket,
        state: dict[str, Any] | None = None,
    ) -> MoverProposal:
        threat = dilate_bool(perception.threat_union, 8)
        dist = distance_to_threat(threat)
        px, py = perception.player_xy
        h, w = threat.shape
        ix, iy = int(np.clip(px, 0, w - 1)), int(np.clip(py, 0, h - 1))
        clearance = float(dist[iy, ix])
        trapped = clearance < 6.0

        now = time.perf_counter()
        if now - self._last_t < self.min_interval_s and self._last_heading != "HOLD":
            return MoverProposal(
                heading=self._last_heading,
                urgency=0.5,
                trapped=trapped,
                clearance_px=clearance,
                debug={"cached": True},
            )

        if not self.api_key:
            prop = self._fallback.propose(perception, intent, state)
            prop.debug["vlm_fallback"] = "no_api_key"
            self._last_heading = prop.heading
            self._last_t = now
            return prop

        try:
            heading = self._call_vlm(perception.frame_bgr, intent)
            if not valid_heading(heading):
                heading = self._fallback.propose(perception, intent, state).heading
        except Exception as exc:  # noqa: BLE001
            prop = self._fallback.propose(perception, intent, state)
            prop.debug["vlm_error"] = str(exc)
            self._last_heading = prop.heading
            self._last_t = now
            return prop

        self._last_heading = heading
        self._last_t = now
        return MoverProposal(
            heading=heading,
            urgency=0.6,
            trapped=trapped,
            clearance_px=clearance,
            debug={"vlm": True},
        )

    def _call_vlm(self, frame_bgr: np.ndarray, intent: IntentPacket) -> str:
        import httpx

        small = cv2.resize(frame_bgr, (256, 192))
        ok, buf = cv2.imencode(".jpg", small, [int(cv2.IMWRITE_JPEG_QUALITY), 70])
        if not ok:
            raise RuntimeError("jpeg encode failed")
        b64 = base64.b64encode(buf.tobytes()).decode("ascii")
        prompt = (
            "You are the movement controller for Vampire Survivors. "
            "Weapons fire automatically; you only choose movement. "
            f"Leader intent: {json.dumps(intent.to_dict())}. "
            'Reply with ONLY JSON: {"move":"N|NE|E|SE|S|SW|W|NW|HOLD"}.'
        )
        payload = {
            "model": self.model,
            "temperature": 0,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
                        },
                    ],
                }
            ],
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        with httpx.Client(timeout=self.timeout_s) as client:
            resp = client.post(f"{self.base_url}/chat/completions", headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
        text = data["choices"][0]["message"]["content"]
        text = text.strip()
        if text.startswith("```"):
            text = text.strip("`")
            if text.startswith("json"):
                text = text[4:].strip()
        parsed = json.loads(text)
        return str(parsed.get("move", "HOLD"))
