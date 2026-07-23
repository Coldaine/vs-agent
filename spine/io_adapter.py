"""io_adapter.py — the ONLY file that talks to the game.

Route abstraction per docs/stack.md. Three candidate backends, tried in
order (A/B/C with one bounded diagnostic cycle each):
  A. NitroGen GamepadEnv (DXcam capture + virtual gamepad + recording)
  B. computer-control-mcp (WGC screenshot + keyboard)
  C. thin MCP facade over NitroGen GamepadEnv

The builder implements the chosen backend behind this interface.
Nothing outside this file may import mcp/dxcam/vgamepad/pydirectinput.

FAIL-SAFE CONTRACT: neutralize() must be callable at any time and must
return all inputs to neutral. run.py calls it in every termination path.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
import time
import numpy as np

DIRECTIONS = ["N", "NE", "E", "SE", "S", "SW", "W", "NW", "HOLD"]


@dataclass
class Frame:
    image: np.ndarray          # BGR
    width: int
    height: int
    t_capture: float           # time.monotonic()


# direction -> held arrow keys (screen coords; +y down)
_DIR_KEYS = {
    "N": ("up",), "S": ("down",), "E": ("right",), "W": ("left",),
    "NE": ("up", "right"), "NW": ("up", "left"),
    "SE": ("down", "right"), "SW": ("down", "left"),
    "HOLD": (),
}
_MENU_KEYS = {"up": "up", "down": "down", "left": "left",
              "right": "right", "confirm": "enter"}


class IOAdapter:
    """Route A backend: dxcam capture (Desktop Duplication — captures
    GPU-accelerated game windows without the black-frame problem that
    kills plain GDI screenshots) + pydirectinput scancode injection
    (Vampire Survivors is keyboard-navigable). This is the ONLY place
    dxcam/pydirectinput/pygetwindow may be imported (AGENTS.md)."""

    def __init__(self, backend: str, config: dict):
        self.backend = backend
        self.config = config
        self._title_hint = (config.get("window_title_hint")
                            or config.get("game_process_hint")
                            or "Vampire Survivors")
        self._held: set[str] = set()
        self._camera = None
        self._region: Optional[tuple] = None

        import pydirectinput
        pydirectinput.PAUSE = 0  # no artificial delay between key events
        self._keys = pydirectinput

    # --- capture ---
    def _ensure_camera(self):
        if self._camera is not None:
            return
        import dxcam
        self._camera = dxcam.create(output_color="BGR")
        self._region = self._window_region()

    def _window_region(self) -> Optional[tuple]:
        """(left, top, right, bottom) of the game window, or None (full
        screen) if the window can't be located."""
        try:
            import pygetwindow as gw
            for w in gw.getAllWindows():
                if self._title_hint.lower() in (w.title or "").lower() and w.width > 0:
                    return (max(w.left, 0), max(w.top, 0),
                            w.left + w.width, w.top + w.height)
        except Exception:
            pass
        return None

    def _focus(self):
        try:
            import pygetwindow as gw
            wins = [w for w in gw.getAllWindows()
                    if self._title_hint.lower() in (w.title or "").lower()]
            if wins:
                w = wins[0]
                if w.isMinimized:
                    w.restore()
                w.activate()
        except Exception:
            pass

    def screenshot(self) -> Frame:
        """Real game frame. Raises BlackFrameError rather than silently
        returning a black frame (GOAL.md G0)."""
        import numpy as _np
        self._ensure_camera()
        img = None
        for _ in range(10):
            img = (self._camera.grab(region=self._region)
                   if self._region else self._camera.grab())
            if img is not None:
                break
            time.sleep(0.01)
        if img is None:                       # no new frame since last grab
            img = getattr(self, "_last_img", None)
        if img is None:
            raise BlackFrameError("capture returned no frame")
        if float(_np.asarray(img).mean()) < 3.0:
            raise BlackFrameError("captured frame is black — check capture "
                                  "path / window focus / resolution")
        self._last_img = img
        h, w = img.shape[:2]
        return Frame(image=img, width=w, height=h, t_capture=time.monotonic())

    # --- input ---
    def _press_keys(self, keys):
        target = set(keys)
        for k in self._held - target:
            self._keys.keyUp(k)
        for k in target - self._held:
            self._keys.keyDown(k)
        self._held = target

    def hold_direction(self, direction: str) -> None:
        """Begin holding a movement direction. Replaces any prior hold.
        'HOLD' = release movement, keep position."""
        self._press_keys(_DIR_KEYS.get(direction, ()))

    def neutralize(self) -> None:
        """ALL inputs to neutral. Idempotent. Called on every exit path."""
        for k in list(self._held):
            try:
                self._keys.keyUp(k)
            except Exception:
                pass
        self._held = set()

    def menu_navigate(self, key: str) -> None:
        """Single discrete menu input: 'up'|'down'|'left'|'right'|'confirm'."""
        self._focus()
        self._keys.press(_MENU_KEYS.get(key, key))

    def click(self, x: int, y: int) -> None:
        self._keys.click(x, y)

    def ocr(self, region: tuple = None) -> str:
        """OCR the current frame or a region [x0, y0, x1, y1].
        Returns text string. Used by launch.py for menu checkpoints."""
        import pytesseract
        frame = self.screenshot()
        img = frame.image
        if region:
            x0, y0, x1, y1 = region
            img = img[y0:y1, x0:x1]
        return pytesseract.image_to_string(img)

    # --- perception helpers ---
    def ocr(self, region: Optional[tuple] = None) -> str:
        import pytesseract
        frame = self.screenshot()
        img = frame.image
        if region:
            x0, y0, x1, y1 = region
            img = img[y0:y1, x0:x1]
        return pytesseract.image_to_string(img)

    def list_windows(self) -> list[dict]:
        try:
            import pygetwindow as gw
            return [{"title": w.title, "left": w.left, "top": w.top,
                     "width": w.width, "height": w.height}
                    for w in gw.getAllWindows() if w.title]
        except Exception:
            return []

    # --- optional frame-step mode (annotation/debug only, never eval) ---
    def pause_process(self) -> None: ...
    def resume_process(self) -> None: ...


class BlackFrameError(RuntimeError):
    pass
