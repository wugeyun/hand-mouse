"""Fine pointer activation and cursor coordinate mapping."""

from __future__ import annotations

from typing import Optional

import numpy as np

from .detectors import HandPose, is_fist, is_index_pointing, is_index_up


POINTER_IDLE = "idle"
POINTER_FINE = "fine"


class PointerModeDetector:
    """Arm fine pointer control and stop immediately for a left fist."""

    def __init__(self, stable_time: float = 0.5) -> None:
        self.stable_time = stable_time
        self.mode = POINTER_IDLE
        self.candidate_since: Optional[float] = None

    def reset(self) -> None:
        self.mode = POINTER_IDLE
        self.candidate_since = None

    def update(self, hands: list[HandPose], now: float) -> str:
        by_hand = {hand.handedness: hand for hand in hands if hand.handedness}
        right = by_hand.get("right")
        left = by_hand.get("left")

        if left is not None and is_fist(left.points):
            self.reset()
            return self.mode

        right_pointing = right is not None and is_index_pointing(right.points)
        if self.mode == POINTER_FINE:
            if right_pointing:
                return self.mode
            self.reset()
            return self.mode

        if right is None or not is_index_up(right.points):
            self.candidate_since = None
            return self.mode
        if self.candidate_since is None:
            self.candidate_since = now
            return self.mode
        if now - self.candidate_since >= self.stable_time:
            self.mode = POINTER_FINE
            self.candidate_since = None
        return self.mode


class CursorMapper:
    """Map right-index movement with a capped nonlinear acceleration curve."""

    def __init__(
        self,
        screen_size: tuple[int, int],
        smoothing: float = 0.35,
        fine_sensitivity: float = 0.35,
        max_gain: float = 3.0,
        acceleration_speed: float = 1.0,
        deadzone: float = 0.0015,
    ) -> None:
        self.width, self.height = screen_size
        self.smoothing = smoothing
        self.fine_sensitivity = fine_sensitivity
        self.max_gain = max(max_gain, fine_sensitivity)
        self.acceleration_speed = max(acceleration_speed, 1e-3)
        self.deadzone = max(deadzone, 0.0)
        self.mode = POINTER_IDLE
        self.cursor_position: Optional[np.ndarray] = None
        self.last_point: Optional[np.ndarray] = None
        self.last_time: Optional[float] = None
        self.filtered_delta = np.zeros(2, dtype=np.float32)

    def set_mode(
        self,
        mode: str,
        pose: Optional[HandPose],
        screen_position: tuple[int, int],
        now: float,
    ) -> None:
        self.mode = mode
        self.cursor_position = np.array(screen_position, dtype=np.float32)
        self.last_point = None
        self.last_time = None
        self.filtered_delta.fill(0)
        if mode == POINTER_FINE and pose is not None:
            self.last_point = pose.points[8, :2].copy()
            self.last_time = now

    def freeze(self, pose: Optional[HandPose], now: float) -> None:
        self.filtered_delta.fill(0)
        if pose is not None:
            self.last_point = pose.points[8, :2].copy()
            self.last_time = now

    def update(self, pose: Optional[HandPose], now: float) -> Optional[tuple[int, int]]:
        if pose is None or self.mode != POINTER_FINE or self.cursor_position is None:
            return None

        point = pose.points[8, :2]
        if self.last_point is None or self.last_time is None:
            self.last_point = point.copy()
            self.last_time = now
            return None

        delta = point - self.last_point
        elapsed = now - self.last_time
        self.last_point = point.copy()
        self.last_time = now
        movement = float(np.linalg.norm(delta))
        if elapsed <= 1e-4 or movement < self.deadzone:
            self.filtered_delta.fill(0)
            return None

        self.filtered_delta += (delta - self.filtered_delta) * self.smoothing
        speed_ratio = min(movement / elapsed / self.acceleration_speed, 1.0)
        gain = self.fine_sensitivity + (self.max_gain - self.fine_sensitivity) * speed_ratio**2
        screen_delta = self.filtered_delta * np.array((self.width, self.height), dtype=np.float32) * gain
        screen_delta[0] = np.clip(screen_delta[0], -self.width * 0.25, self.width * 0.25)
        screen_delta[1] = np.clip(screen_delta[1], -self.height * 0.25, self.height * 0.25)
        self.cursor_position += screen_delta
        self.cursor_position[0] = np.clip(self.cursor_position[0], 0, self.width - 1)
        self.cursor_position[1] = np.clip(self.cursor_position[1], 0, self.height - 1)
        return int(self.cursor_position[0]), int(self.cursor_position[1])
