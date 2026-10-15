"""Fine pointer activation and cursor coordinate mapping."""

from __future__ import annotations

import numpy as np

from .controller import DisplayBounds
from .detectors import HandPose, is_open_palm

POINTER_IDLE = "idle"
POINTER_FINE = "fine"


class PalmPointerDetector:
    """Enter pointer mode after a stable right open palm; stop on loss or closing."""

    def __init__(self, stable_time: float = 0.3) -> None:
        self.stable_time = stable_time
        self.mode = POINTER_IDLE
        self.candidate_since: float | None = None

    def reset(self) -> None:
        self.mode = POINTER_IDLE
        self.candidate_since = None

    def update(self, hands: list[HandPose], now: float) -> str:
        right = next((hand for hand in hands if hand.handedness == "right"), None)
        if right is None or not is_open_palm(right):
            self.reset()
            return self.mode
        if self.candidate_since is None:
            self.candidate_since = now
        if now - self.candidate_since >= self.stable_time:
            self.mode = POINTER_FINE
        return self.mode


PointerModeDetector = PalmPointerDetector


class CursorMapper:
    """Map the camera's full normalized range to one display without a jump."""

    def __init__(
        self,
        screen_size: DisplayBounds | tuple[int, int],
        smoothing: float = 0.35,
        fine_sensitivity: float = 0.35,
        max_gain: float = 3.0,
        acceleration_speed: float = 1.0,
        deadzone: float = 0.0015,
        transition_duration: float = 0.35,
    ) -> None:
        self.display = self._coerce_display(screen_size)
        self.width, self.height = self.display.width, self.display.height
        self.smoothing = float(np.clip(smoothing, 0.0, 1.0))
        self.fine_sensitivity = max(float(fine_sensitivity), 1e-3)
        self.max_gain = max(float(max_gain), self.fine_sensitivity)
        self.acceleration_speed = max(float(acceleration_speed), 1e-3)
        self.deadzone = max(float(deadzone), 0.0)
        self.transition_duration = max(float(transition_duration), 1e-3)
        self.mode = POINTER_IDLE
        self.cursor_position: np.ndarray | None = None
        self.last_point: np.ndarray | None = None
        self.last_time: float | None = None
        self.filtered_target: np.ndarray | None = None
        self.target_point: np.ndarray | None = None
        self.transition_offset = np.zeros(2, dtype=np.float32)

    @staticmethod
    def _coerce_display(display: DisplayBounds | tuple[int, int]) -> DisplayBounds:
        if isinstance(display, DisplayBounds):
            return display
        width, height = display
        return DisplayBounds(0, 0, int(width), int(height), is_primary=True)

    def _set_display(self, display: DisplayBounds | tuple[int, int]) -> None:
        self.display = self._coerce_display(display)
        self.width, self.height = self.display.width, self.display.height

    def _target_for_point(self, point: np.ndarray) -> np.ndarray:
        normalized = np.clip(point, 0.0, 1.0)
        return np.array(
            (
                self.display.x + normalized[0] * (self.display.width - 1),
                self.display.y + normalized[1] * (self.display.height - 1),
            ),
            dtype=np.float32,
        )

    def _clamp_position(self, position: np.ndarray) -> np.ndarray:
        return np.array(
            (
                np.clip(position[0], self.display.x, self.display.x + self.display.width - 1),
                np.clip(position[1], self.display.y, self.display.y + self.display.height - 1),
            ),
            dtype=np.float32,
        )

    def set_mode(
        self,
        mode: str,
        control_point: np.ndarray | None,
        screen_position: tuple[int, int],
        now: float,
        display: DisplayBounds | tuple[int, int] | None = None,
    ) -> None:
        if display is not None:
            self._set_display(display)
        self.mode = mode
        self.cursor_position = np.array(screen_position, dtype=np.float32)
        self.last_point = None
        self.last_time = None
        self.filtered_target = None
        self.target_point = None
        self.transition_offset.fill(0)
        if mode == POINTER_FINE and control_point is not None:
            point = np.asarray(control_point, dtype=np.float32).copy()
            target = self._target_for_point(point)
            self.filtered_target = target
            self.target_point = point.copy()
            self.transition_offset = self.cursor_position - target
            self.last_point = point
            self.last_time = now

    def freeze(self, control_point: np.ndarray | None, now: float) -> None:
        if control_point is not None:
            self.last_point = np.asarray(control_point, dtype=np.float32).copy()
            self.last_time = now

    def update(self, control_point: np.ndarray | None, now: float) -> tuple[int, int] | None:
        if control_point is None or self.mode != POINTER_FINE or self.cursor_position is None:
            return None

        point = np.asarray(control_point, dtype=np.float32)
        if self.last_point is None or self.last_time is None:
            self.last_point = point.copy()
            self.last_time = now
            return None

        delta = point - self.last_point
        elapsed = now - self.last_time
        self.last_point = point.copy()
        self.last_time = now
        movement = float(np.linalg.norm(delta))
        if elapsed <= 1e-4 or self.filtered_target is None or self.target_point is None:
            return None

        # Compare with the last accepted point so slow motion can accumulate.
        if float(np.linalg.norm(point - self.target_point)) >= self.deadzone:
            self.target_point = point.copy()
        target = self._target_for_point(self.target_point)
        self.filtered_target += (target - self.filtered_target) * self.smoothing

        speed_ratio = min(movement / elapsed / self.acceleration_speed, 1.0)
        gain = self.fine_sensitivity + (self.max_gain - self.fine_sensitivity) * speed_ratio**2
        follow_alpha = min(1.0, gain)
        transition_alpha = min(1.0, elapsed / self.transition_duration)
        self.transition_offset *= 1.0 - transition_alpha
        target = self._clamp_position(self.filtered_target + self.transition_offset)
        self.cursor_position += (target - self.cursor_position) * follow_alpha
        self.cursor_position = self._clamp_position(self.cursor_position)
        return round(float(self.cursor_position[0])), round(float(self.cursor_position[1]))
