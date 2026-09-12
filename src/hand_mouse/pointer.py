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
    """Map right-index relative movement to fine cursor movement."""

    def __init__(
        self,
        screen_size: tuple[int, int],
        smoothing: float = 0.35,
        fine_sensitivity: float = 0.35,
    ) -> None:
        self.width, self.height = screen_size
        self.smoothing = smoothing
        self.fine_sensitivity = fine_sensitivity
        self.mode = POINTER_IDLE
        self.smoothed: Optional[np.ndarray] = None
        self.fine_origin: Optional[np.ndarray] = None
        self.fine_screen_origin: Optional[np.ndarray] = None

    def set_mode(self, mode: str, pose: Optional[HandPose], screen_position: tuple[int, int]) -> None:
        self.mode = mode
        self.smoothed = None
        self.fine_origin = None
        self.fine_screen_origin = None
        if mode == POINTER_FINE and pose is not None:
            self.fine_origin = pose.points[8, :2].copy()
            self.fine_screen_origin = np.array(screen_position, dtype=np.float32)

    def update(self, pose: Optional[HandPose]) -> Optional[tuple[int, int]]:
        if (
            pose is None
            or self.mode != POINTER_FINE
            or self.fine_origin is None
            or self.fine_screen_origin is None
        ):
            return None

        point = pose.points[8, :2]
        delta = (point - self.fine_origin) * np.array((self.width, self.height), dtype=np.float32)
        target = self.fine_screen_origin + delta * self.fine_sensitivity
        target[0] = np.clip(target[0], 0, self.width - 1)
        target[1] = np.clip(target[1], 0, self.height - 1)
        if self.smoothed is None:
            self.smoothed = target
        else:
            self.smoothed += (target - self.smoothed) * self.smoothing
        return int(self.smoothed[0]), int(self.smoothed[1])
