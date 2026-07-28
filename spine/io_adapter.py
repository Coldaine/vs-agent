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
import ctypes
from ctypes import wintypes
import gc
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
               "right": "right", "confirm": "enter", "start": "space"}
_GAMEPAD_DIRECTIONS = {
    "N": (0, 32767), "S": (0, -32768), "E": (32767, 0), "W": (-32768, 0),
    "NE": (23170, 23170), "NW": (-23170, 23170),
    "SE": (23170, -23170), "SW": (-23170, -23170), "HOLD": (0, 0),
}


class _XINPUT_GAMEPAD(ctypes.Structure):
    _fields_ = [
        ("wButtons", wintypes.WORD),
        ("bLeftTrigger", wintypes.BYTE),
        ("bRightTrigger", wintypes.BYTE),
        ("sThumbLX", wintypes.SHORT),
        ("sThumbLY", wintypes.SHORT),
        ("sThumbRX", wintypes.SHORT),
        ("sThumbRY", wintypes.SHORT),
    ]


class _XINPUT_STATE(ctypes.Structure):
    _fields_ = [("dwPacketNumber", wintypes.DWORD), ("Gamepad", _XINPUT_GAMEPAD)]


_XINPUT = None


def _xinput():
    global _XINPUT
    if _XINPUT is not None:
        return _XINPUT
    for name in ("xinput1_4.dll", "xinput1_3.dll", "xinput9_1_0.dll"):
        try:
            _XINPUT = ctypes.WinDLL(name)
            _XINPUT.XInputGetState.argtypes = [
                wintypes.DWORD, ctypes.POINTER(_XINPUT_STATE)
            ]
            _XINPUT.XInputGetState.restype = wintypes.DWORD
            return _XINPUT
        except OSError:
            continue
    raise GamepadUnavailableError("no XInput DLL is available")


def _connected_xinput_slots() -> set[int]:
    xinput = _xinput()
    state = _XINPUT_STATE()
    connected = set()
    for slot in range(4):
        if xinput.XInputGetState(slot, ctypes.byref(state)) == 0:
            connected.add(slot)
    return connected


class IOAdapter:
    """Route A backend: WGC/DXcam capture plus keyboard or ViGEm virtual
    Xbox 360 input. This is the ONLY place dxcam/pydirectinput/pygetwindow/
    vgamepad may be imported (AGENTS.md)."""

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
        self._input_backend = config.get("input_backend", "gamepad")
        self._gamepad = None
        self._gamepad_ready_timeout_s = float(config.get(
            "gamepad_ready_timeout_s", config.get("gamepad_ready_delay_s", 0.75)))
        self._gamepad_create_retries = int(config.get("gamepad_create_retries", 3))
        self._gamepad_recreate_on_error = bool(config.get("gamepad_recreate_on_error", True))
        self._gamepad_recoveries = 0
        self._recovering_gamepad = False

        import pydirectinput
        pydirectinput.PAUSE = 0  # no artificial delay between key events
        self._keys = pydirectinput
        if self._input_backend == "gamepad":
            self._create_gamepad()

    def _create_gamepad(self) -> None:
        try:
            import vgamepad as vg
        except Exception as error:
            raise GamepadUnavailableError(
                f"vgamepad is unavailable: {error}"
            ) from error
        self._vg = vg
        attempts = max(1, self._gamepad_create_retries)
        timeout_s = max(0.1, self._gamepad_ready_timeout_s)
        last_error = None
        for attempt in range(1, attempts + 1):
            baseline = _connected_xinput_slots()
            gamepad = None
            try:
                gamepad = vg.VX360Gamepad()
                gamepad.update()
                deadline = time.monotonic() + timeout_s
                while time.monotonic() < deadline:
                    connected = _connected_xinput_slots()
                    if connected - baseline or (not baseline and connected):
                        self._gamepad = gamepad
                        return
                    time.sleep(0.05)
                raise GamepadUnavailableError(
                    "virtual Xbox 360 controller was not enumerated by XInput "
                    f"within {timeout_s:.2f}s")
            except Exception as error:
                last_error = error
                if gamepad is not None:
                    try:
                        gamepad.reset()
                        gamepad.update()
                    except Exception:
                        pass
                    del gamepad
                    gc.collect()
                if attempt < attempts:
                    time.sleep(0.25 * attempt)
        raise GamepadUnavailableError(
            "could not create a ViGEm virtual Xbox 360 controller after "
            f"{attempts} attempts: {last_error}")

    def _destroy_gamepad(self) -> None:
        gamepad = self._gamepad
        self._gamepad = None
        if gamepad is None:
            return
        try:
            gamepad.reset()
            gamepad.update()
        except Exception:
            pass
        del gamepad
        gc.collect()

    def _recover_gamepad(self, error: Exception) -> None:
        if self._recovering_gamepad:
            raise GamepadUnavailableError(
                f"gamepad recovery failed while probing an existing recovery: {error}"
            ) from error
        self._recovering_gamepad = True
        try:
            self._destroy_gamepad()
            self._create_gamepad()
            self._gamepad_recoveries += 1
            print(f"[gamepad] recreated after input failure: {error}")
        finally:
            self._recovering_gamepad = False

    def _with_gamepad(self, action) -> None:
        if self._gamepad is None:
            self._create_gamepad()
        try:
            action(self._gamepad)
            self._gamepad.update()
        except Exception as error:
            if not self._gamepad_recreate_on_error:
                raise
            self._recover_gamepad(error)
            action(self._gamepad)
            self._gamepad.update()

    def _tap_gamepad_button(self, button) -> None:
        self._with_gamepad(lambda gamepad: gamepad.press_button(button=button))
        time.sleep(float(self.config.get("gamepad_button_hold_s", 0.3)))
        self._with_gamepad(lambda gamepad: gamepad.release_button(button=button))

    def close(self) -> None:
        self.neutralize()
        self._destroy_gamepad()

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
        if self._input_backend == "gamepad":
            x_value, y_value = _GAMEPAD_DIRECTIONS.get(direction, (0, 0))
            self._with_gamepad(
                lambda gamepad: gamepad.left_joystick(
                    x_value=x_value, y_value=y_value))
            return
        self._press_keys(_DIR_KEYS.get(direction, ()))

    def neutralize(self) -> None:
        """ALL inputs to neutral. Idempotent. Called on every exit path."""
        if self._gamepad is not None:
            try:
                self._gamepad.reset()
                self._gamepad.update()
            except Exception:
                pass
        for k in list(self._held):
            try:
                self._keys.keyUp(k)
            except Exception:
                pass
        self._held = set()

    def menu_navigate(self, key: str) -> None:
        """Single discrete menu input: 'up'|'down'|'left'|'right'|'confirm'."""
        self._focus()
        if self._input_backend == "gamepad":
            buttons = {
                "up": self._vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_UP,
                "down": self._vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_DOWN,
                "left": self._vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_LEFT,
                "right": self._vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_RIGHT,
                "confirm": self._vg.XUSB_BUTTON.XUSB_GAMEPAD_A,
                "start": self._vg.XUSB_BUTTON.XUSB_GAMEPAD_START,
                "esc": self._vg.XUSB_BUTTON.XUSB_GAMEPAD_B,
            }
            button = buttons.get(key)
            if button is None:
                raise ValueError(f"unsupported gamepad menu key: {key}")
            self._tap_gamepad_button(button)
            return
        mapped = _MENU_KEYS.get(key, key)
        # Vampire Survivors ignores zero-duration synthetic menu presses.
        self._keys.keyDown(mapped)
        time.sleep(0.12)
        self._keys.keyUp(mapped)

    def click(self, x: int, y: int) -> None:
        self._keys.click(x, y)

    def click_frame(self, x: int, y: int) -> None:
        """Click frame coordinates relative to the captured game window.

        Applies the calibrated capture-to-hit-test transform and fails closed
        when the live capture resolution no longer matches calibration.
        """
        import ctypes

        from capture_transform import frame_to_hit_test

        frame_size = None
        try:
            frame = self.screenshot()
            frame_size = (frame.width, frame.height)
        except Exception:
            # Fall back to configured calibration resolution when capture is
            # temporarily unavailable; frame_to_hit_test still applies scale.
            expected = self.config.get("capture_calibration_resolution")
            if expected is not None:
                frame_size = (int(expected[0]), int(expected[1]))

        hit_x, hit_y = frame_to_hit_test(
            x, y, self.config, frame_size=frame_size
        )
        window = self._game_window()
        if window is not None:
            origin_x, origin_y = window.left, window.top
        else:
            origin_x, origin_y = self.config.get("wgc_monitor_origin", [0, 0])
        user32 = ctypes.windll.user32
        user32.SetCursorPos(int(origin_x + hit_x), int(origin_y + hit_y))
        user32.mouse_event(0x0002, 0, 0, 0, 0)
        user32.mouse_event(0x0004, 0, 0, 0, 0)

    # --- perception helpers ---
    def ocr(self, region: Optional[tuple] = None, ocr_config: str | None = None) -> str:
        import pytesseract
        tesseract_cmd = self.config.get("tesseract_cmd")
        if tesseract_cmd:
            pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
        frame = self.screenshot()
        img = frame.image
        if region:
            x0, y0, x1, y1 = region
            img = img[y0:y1, x0:x1]
        config = self.config.get("menu_ocr_config", "") if ocr_config is None else ocr_config
        return pytesseract.image_to_string(img, config=config)

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


class GamepadUnavailableError(RuntimeError):
    pass


class BlackFrameError(RuntimeError):
    pass
