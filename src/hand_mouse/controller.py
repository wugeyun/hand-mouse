"""Operating-system input events used by the gesture application."""

from __future__ import annotations

from typing import Callable


class InputController:
    def __init__(self, live: bool, scroll_amount: int) -> None:
        try:
            import pyautogui
        except ImportError as exc:
            if live:
                raise RuntimeError("pyautogui is required; install the project dependencies first") from exc
            pyautogui = None

        self.pyautogui = pyautogui
        self.live = live
        self.scroll_amount = scroll_amount
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

    def left_click(self) -> None:
        self._emit("left click", lambda: self.pyautogui.click())
