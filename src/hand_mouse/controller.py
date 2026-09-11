"""Operating-system input events used by the gesture application."""

from __future__ import annotations

import platform
from typing import Callable


class InputController:
    def __init__(self, live: bool, scroll_amount: int, zoom_amount: int, zoom_mode: str) -> None:
        try:
            import pyautogui
        except ImportError as exc:
            if live:
                raise RuntimeError("pyautogui is required; install the project dependencies first") from exc
            pyautogui = None

        self.pyautogui = pyautogui
        self.live = live
        self.scroll_amount = scroll_amount
        self.zoom_amount = zoom_amount
        self.zoom_mode = zoom_mode
        self.modifier = "command" if platform.system() == "Darwin" else "ctrl"
        if self.pyautogui is not None:
            self.pyautogui.PAUSE = 0.01
            self.pyautogui.FAILSAFE = True

    def _emit(self, label: str, callback: Callable[[], None]) -> None:
        mode = "LIVE" if self.live else "DRY-RUN"
        print(f"[{mode}] {label}", flush=True)
        if self.live:
            callback()

    def scroll(self, direction: int) -> None:
        self._emit(
            f"scroll {'up' if direction > 0 else 'down'}",
            lambda: self.pyautogui.scroll(direction * self.scroll_amount),
        )

    def zoom(self, direction: int) -> None:
        def send_zoom() -> None:
            if self.zoom_mode == "keys":
                key = "=" if direction > 0 else "-"
                self.pyautogui.hotkey(self.modifier, key)
                return

            self.pyautogui.keyDown(self.modifier)
            try:
                self.pyautogui.scroll(direction * self.zoom_amount)
            finally:
                self.pyautogui.keyUp(self.modifier)

        self._emit(
            f"zoom {'in' if direction > 0 else 'out'} ({self.zoom_mode})",
            send_zoom,
        )

    def left_click(self) -> None:
        self._emit("left click", lambda: self.pyautogui.click())

    def right_click(self) -> None:
        self._emit("right click", lambda: self.pyautogui.rightClick())
