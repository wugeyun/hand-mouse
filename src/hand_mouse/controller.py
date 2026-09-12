"""Operating-system input events used by the gesture application."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class DisplayBounds:
    """A full display rectangle in the desktop's global coordinate space."""

    x: int
    y: int
    width: int
    height: int
    is_primary: bool | None = None

    def __post_init__(self) -> None:
        if self.width <= 0 or self.height <= 0:
            raise ValueError("display dimensions must be positive")

    def contains(self, position: tuple[int, int]) -> bool:
        x, y = position
        return self.x <= x < self.x + self.width and self.y <= y < self.y + self.height


def select_display(position: tuple[int, int], displays: tuple[DisplayBounds, ...]) -> DisplayBounds:
    """Select the display containing a pointer, or the nearest display for a gap."""
    if not displays:
        raise ValueError("at least one display is required")
    for display in displays:
        if display.contains(position):
            return display

    def distance(display: DisplayBounds) -> tuple[int, int]:
        x, y = position
        right = display.x + display.width - 1
        bottom = display.y + display.height - 1
        dx = max(display.x - x, 0, x - right)
        dy = max(display.y - y, 0, y - bottom)
        return dx * dx + dy * dy, 0 if display.is_primary else 1

    return min(displays, key=distance)


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
        self.last_position: tuple[int, int] | None = None
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

    def right_click(self) -> None:
        self._emit("right click", lambda: self.pyautogui.rightClick())

    def _fallback_display(self) -> DisplayBounds:
        if self.pyautogui is None:
            return DisplayBounds(0, 0, 1920, 1080, is_primary=True)
        width, height = self.pyautogui.size()
        return DisplayBounds(0, 0, int(width), int(height), is_primary=True)

    def displays(self) -> tuple[DisplayBounds, ...]:
        """Return full display bounds, falling back to the primary display."""
        try:
            from screeninfo import get_monitors
            from screeninfo.common import ScreenInfoError
        except ImportError:
            monitors = []
        else:
            try:
                monitors = get_monitors()
            except (OSError, RuntimeError, ScreenInfoError):
                monitors = []

        displays = tuple(
            DisplayBounds(
                int(monitor.x),
                int(monitor.y),
                int(monitor.width),
                int(monitor.height),
                is_primary=getattr(monitor, "is_primary", None),
            )
            for monitor in monitors
            if monitor.width > 0 and monitor.height > 0
        )
        return displays or (self._fallback_display(),)

    def display_for_position(self, position: tuple[int, int]) -> DisplayBounds:
        return select_display(position, self.displays())

    def _default_display(self) -> DisplayBounds:
        displays = self.displays()
        return next((item for item in displays if item.is_primary), displays[0])

    def screen_size(self) -> tuple[int, int]:
        display = self._default_display()
        return display.width, display.height

    def position(self) -> tuple[int, int]:
        if self.live and self.pyautogui is not None:
            x, y = self.pyautogui.position()
            self.last_position = int(x), int(y)
        if self.last_position is not None:
            return self.last_position
        display = self._default_display()
        return display.x + display.width // 2, display.y + display.height // 2

    def move_cursor(self, position: tuple[int, int]) -> None:
        self.last_position = position
        if self.live and self.pyautogui is not None:
            self.pyautogui.moveTo(position[0], position[1], duration=0)
