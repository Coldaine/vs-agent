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


def _enable_per_monitor_dpi_awareness() -> None:
    """Keep Win32 window coordinates in DXCam's physical-pixel space."""
    try:
        import ctypes
        ctypes.windll.user32.SetProcessDpiAwarenessContext(-4)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


_enable_per_monitor_dpi_awareness()

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
        self.config = config
        configured_backend = config.get("capture_backend", "wgc")
        self.backend = (backend if backend in {"wgc", "dxcam"}
                        else configured_backend)
        self._title_hint = (config.get("window_title_hint")
                            or config.get("game_process_hint")
                            or "Vampire Survivors")
        self._held: set[str] = set()
        self._camera = None
        self._region: Optional[tuple] = None
        self._capture_output_idx = int(config.get("capture_output_idx", 0))
        minimum = config.get("capture_min_dimensions", [640, 480])
        self._min_capture_width, self._min_capture_height = minimum
        self._capture_retries = int(config.get("capture_retries", 3))
        self._last_img: Optional[np.ndarray] = None

        import pydirectinput
        pydirectinput.PAUSE = 0  # no artificial delay between key events
        self._keys = pydirectinput

    # --- capture ---
    def _ensure_camera(self):
        if self.backend == "wgc":
            return
        if self._camera is not None:
            return
        import dxcam
        self._region = self._window_region()
        self._camera = dxcam.create(output_idx=self._capture_output_idx,
                                    output_color="BGR")

    def _game_window(self):
        """Prefer the exact game title so an IDE project window is never captured."""
        import pygetwindow as gw
        windows = [w for w in gw.getAllWindows()
                   if w.width > 0 and w.height > 0]
        exact = [w for w in windows if (w.title or "").strip().lower()
                 == self._title_hint.lower()]
        if exact:
            return exact[0]
        matches = [w for w in windows if self._title_hint.lower()
                   in (w.title or "").lower()]
        return matches[0] if matches else None

    @staticmethod
    def _monitor_bounds(window) -> tuple[int, int, int, int]:
        """Return virtual-desktop bounds for the monitor containing a window."""
        import ctypes
        from ctypes import wintypes

        class RECT(ctypes.Structure):
            _fields_ = [("left", wintypes.LONG), ("top", wintypes.LONG),
                        ("right", wintypes.LONG), ("bottom", wintypes.LONG)]

        class MONITORINFO(ctypes.Structure):
            _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", RECT),
                        ("rcWork", RECT), ("dwFlags", wintypes.DWORD)]

        monitor = ctypes.windll.user32.MonitorFromWindow(window._hWnd, 2)
        info = MONITORINFO()
        info.cbSize = ctypes.sizeof(info)
        if not ctypes.windll.user32.GetMonitorInfoW(monitor, ctypes.byref(info)):
            raise OSError("GetMonitorInfoW failed for game window")
        rect = info.rcMonitor
        return rect.left, rect.top, rect.right, rect.bottom

    def _window_region(self) -> tuple:
        """Game crop in DXCam-output coordinates, including negative monitors."""
        window = self._game_window()
        if window is None:
            raise RuntimeError(f"game window {self._title_hint!r} not found")
        left, top, right, bottom = self._monitor_bounds(window)
        x0 = max(window.left - left, 0)
        y0 = max(window.top - top, 0)
        x1 = min(window.left + window.width - left, right - left)
        y1 = min(window.top + window.height - top, bottom - top)
        if x1 <= x0 or y1 <= y0:
            raise RuntimeError("game window has no visible monitor region")
        return x0, y0, x1, y1

    def _wgc_screenshot(self) -> np.ndarray:
        """Capture the exact game window even when it is occluded."""
        import cv2
        from computer_control_mcp.core import _wgc_screenshot

        result = _wgc_screenshot(self._title_hint)
        if result is None:
            raise BlackFrameError("WGC could not capture the game window")
        data, _, _ = result
        image = cv2.imdecode(np.frombuffer(data, dtype=np.uint8),
                             cv2.IMREAD_COLOR)
        if image is None:
            raise BlackFrameError("WGC returned an unreadable game frame")
        return image

    def _focus(self):
        import ctypes
        window = self._game_window()
        if window is None:
            raise RuntimeError(f"game window {self._title_hint!r} not found")
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        for _ in range(3):
            foreground = user32.GetForegroundWindow()
            current_thread = kernel32.GetCurrentThreadId()
            foreground_thread = user32.GetWindowThreadProcessId(foreground, None)
            user32.AttachThreadInput(current_thread, foreground_thread, True)
            try:
                user32.ShowWindow(window._hWnd, 9)
                user32.BringWindowToTop(window._hWnd)
                user32.SetForegroundWindow(window._hWnd)
            finally:
                user32.AttachThreadInput(current_thread, foreground_thread, False)
            time.sleep(0.15)
            if user32.GetForegroundWindow() == window._hWnd:
                return
        raise RuntimeError("Windows rejected game foreground activation")

    def _capture_image(self) -> np.ndarray | None:
        self._ensure_camera()
        if self.backend == "wgc":
            return self._wgc_screenshot()
        img = None
        for _ in range(10):
            img = (self._camera.grab(region=self._region)
                   if self._region else self._camera.grab())
            if img is not None:
                break
            time.sleep(0.01)
        return img

    def screenshot(self) -> Frame:
        """Return a valid game frame, retrying transient WGC resize glitches."""
        last_error = "capture returned no frame"
        for attempt in range(1, self._capture_retries + 1):
            try:
                img = self._capture_image()
                if img is None:
                    raise BlackFrameError("capture returned no frame")
                if float(np.asarray(img).mean()) < 3.0:
                    raise BlackFrameError("captured frame is black")
                height, width = img.shape[:2]
                if (width < self._min_capture_width
                        or height < self._min_capture_height):
                    raise BlackFrameError(
                        f"capture is unexpectedly small ({width}x{height})")
                self._last_img = img
                return Frame(image=img, width=width, height=height,
                             t_capture=time.monotonic())
            except BlackFrameError as error:
                last_error = str(error)
                if attempt < self._capture_retries:
                    time.sleep(0.15)

        if self._last_img is not None:
            height, width = self._last_img.shape[:2]
            print(f"[capture] retry exhaustion ({last_error}); using last good frame")
            return Frame(image=self._last_img, width=width, height=height,
                         t_capture=time.monotonic())
        raise BlackFrameError(last_error)

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

    # --- perception helpers ---
    def ocr(self, region: Optional[tuple] = None) -> str:
        import pytesseract
        tesseract_cmd = self.config.get("tesseract_cmd")
        if tesseract_cmd:
            pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
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
