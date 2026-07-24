from __future__ import annotations

import logging
import threading

logger = logging.getLogger(__name__)


class KillSwitch:
    """Deadman switch: press configured key (default F8) to stop the harness."""

    def __init__(self, key_name: str = "F8"):
        self.key_name = key_name.upper()
        self.triggered = False
        self._listener = None
        self._start()

    def _start(self) -> None:
        try:
            from pynput import keyboard  # type: ignore
        except Exception:
            logger.info("KillSwitch: pynput unavailable; use Ctrl+C")
            return

        key_attr = getattr(keyboard.Key, self.key_name.lower(), None)

        def on_press(key):  # noqa: ANN001
            try:
                if key_attr is not None and key == key_attr:
                    self.triggered = True
                    logger.warning("Kill switch %s pressed — stopping", self.key_name)
                    return False
            except Exception:
                return None
            return None

        self._listener = keyboard.Listener(on_press=on_press)
        self._listener.daemon = True
        self._listener.start()

    def stop(self) -> None:
        if self._listener is not None:
            try:
                self._listener.stop()
            except Exception:
                pass
