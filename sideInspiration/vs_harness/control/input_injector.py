from __future__ import annotations

import logging
from typing import Iterable

logger = logging.getLogger(__name__)


class InputInjector:
    """Holds WASD / menu keys. Live backends optional; sim uses set callback."""

    def __init__(self, live: bool = False, on_keys=None):
        self.live = live
        self.on_keys = on_keys
        self.held: set[str] = set()
        self._backend = None
        if live:
            self._init_live()

    def _init_live(self) -> None:
        try:
            from pynput.keyboard import Controller, KeyCode  # type: ignore

            self._backend = ("pynput", Controller(), KeyCode)
        except Exception:
            logger.warning("pynput unavailable; input injector in dry-run mode")
            self.live = False

    def set_keys(self, keys: Iterable[str]) -> None:
        new = {k.lower() for k in keys}
        if self.on_keys is not None:
            self.on_keys(new)
        if not self.live or self._backend is None:
            self.held = new
            return
        kind, ctrl, KeyCode = self._backend
        assert kind == "pynput"
        for k in self.held - new:
            ctrl.release(KeyCode.from_char(k))
        for k in new - self.held:
            ctrl.press(KeyCode.from_char(k))
        self.held = new

    def tap(self, key: str) -> None:
        if self.on_keys is not None:
            self.on_keys({key})
        if not self.live or self._backend is None:
            return
        kind, ctrl, KeyCode = self._backend
        ctrl.press(KeyCode.from_char(key))
        ctrl.release(KeyCode.from_char(key))

    def release_all(self) -> None:
        self.set_keys([])
