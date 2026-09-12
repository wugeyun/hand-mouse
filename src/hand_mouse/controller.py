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
        self.last_position = None
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

    def screen_size(self) -> tuple[int, int]:
        if self.pyautogui is None:
            return 1920, 1080
        width, height = self.pyautogui.size()
        return int(width), int(height)

    def position(self) -> tuple[int, int]:
        if self.live and self.pyautogui is not None:
            x, y = self.pyautogui.position()
            self.last_position = int(x), int(y)
        if self.last_position is not None:
            return self.last_position
        width, height = self.screen_size()
        return width // 2, height // 2

    def move_cursor(self, position: tuple[int, int]) -> None:
        self.last_position = position
        if self.live and self.pyautogui is not None:
            self.pyautogui.moveTo(position[0], position[1], duration=0)
