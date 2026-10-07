"""Fine pointer activation and cursor coordinate mapping."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from .controller import DisplayBounds
from .detectors import HandPose, is_thumb_index_pinch

POINTER_IDLE = "idle"
POINTER_FINE = "fine"


class PinchPointerDetector:
    """Enter pointer mode after a stable right thumb-index pinch."""

    def __init__(self, stable_time: float = 0.3) -> None:
        self.stable_time = stable_time
        self.mode = POINTER_IDLE
        self.candidate_since: float | None = None

    def reset(self) -> None:
        self.mode = POINTER_IDLE
        self.candidate_since = None

    def update(self, hands: list[HandPose], now: float) -> str:
        by_hand = {hand.handedness: hand for hand in hands if hand.handedness}
        right = by_hand.get("right")
        right_pinching = right is not None and is_thumb_index_pinch(right.points, right.box_scale)
        if self.mode == POINTER_FINE:
            if right is None or right_pinching:
                return self.mode
            self.reset()
            return self.mode

        if right is None or not right_pinching:
            self.candidate_since = None
            return self.mode
        if self.candidate_since is None:
            self.candidate_since = now
            return self.mode
        if now - self.candidate_since >= self.stable_time:
            self.mode = POINTER_FINE
            self.candidate_since = None
        return self.mode


PointerModeDetector = PinchPointerDetector


@dataclass
class _TrackedTip:
    tracker: Any
    offset: np.ndarray


class PinchPointTracker:
    """Track the two pinched fingertips after the full hand leaves the frame."""

    def __init__(self, pinch_threshold_ratio: float = 0.45) -> None:
        self.pinch_threshold_ratio = max(float(pinch_threshold_ratio), 0.05)
        self._tips: tuple[_TrackedTip, _TrackedTip] | None = None
        self._frame_size: tuple[int, int] | None = None
        self._pinch_limit_pixels = 0.0
        self._reference: tuple[Any, np.ndarray, float] | None = None

    @property
    def active(self) -> bool:
        return self._tips is not None or self._reference is not None

    def reset(self) -> None:
        self._tips = None
        self._frame_size = None
        self._pinch_limit_pixels = 0.0
        self._reference = None

    def remember(self, frame: Any, points: np.ndarray, box_scale: float) -> None:
        """Save reliable landmarks; create local trackers only if the hand is lost."""
        self.reset()
        self._reference = frame.copy(), points.copy(), box_scale

    @staticmethod
    def _create_tracker() -> Any | None:
        try:
            import cv2
        except ImportError:
            return None

        factory = getattr(cv2, "TrackerCSRT_create", None)
        if factory is None:
            legacy = getattr(cv2, "legacy", None)
            factory = getattr(legacy, "TrackerCSRT_create", None) if legacy is not None else None
        return factory() if factory is not None else None

    @staticmethod
    def _tip_box(
        point: np.ndarray,
        width: int,
        height: int,
        side: int,
    ) -> tuple[tuple[int, int, int, int], np.ndarray]:
        pixel = np.array((point[0] * (width - 1), point[1] * (height - 1)), dtype=np.float32)
        left = round(float(pixel[0] - side / 2))
        top = round(float(pixel[1] - side / 2))
        left = max(0, min(left, width - side))
        top = max(0, min(top, height - side))
        center = np.array((left + side / 2, top + side / 2), dtype=np.float32)
        return (left, top, side, side), pixel - center

    def start(self, frame: Any, points: np.ndarray, box_scale: float) -> bool:
        """Initialize two local trackers from normalized thumb and index points."""
        self.reset()
        height, width = frame.shape[:2]
        if width < 16 or height < 16:
            return False

        minimum_dimension = min(width, height)
        half_side = int(np.clip(float(box_scale) * minimum_dimension * 0.20, 10, 40))
        side = min(max(half_side * 2, 16), width, height)
        tracked_tips: list[_TrackedTip] = []
        for point in (points[4, :2], points[8, :2]):
            tracker = self._create_tracker()
            if tracker is None:
                self.reset()
                return False
            box, offset = self._tip_box(point, width, height, side)
            try:
                initialized = tracker.init(frame, box)
            except Exception:  # noqa: BLE001 - OpenCV backends expose platform-specific types.
                self.reset()
                return False
            if initialized is False:
                self.reset()
                return False
            tracked_tips.append(_TrackedTip(tracker=tracker, offset=offset))

        self._tips = tracked_tips[0], tracked_tips[1]
        self._frame_size = width, height
        self._pinch_limit_pixels = max(
            float(side) * 1.25,
            float(box_scale) * minimum_dimension * self.pinch_threshold_ratio,
        )
        return True

    def update(self, frame: Any) -> np.ndarray | None:
        """Return a normalized pinch midpoint, or stop when tracking loses either tip."""
        if self._reference is not None:
            reference_frame, points, box_scale = self._reference
            if not self.start(reference_frame, points, box_scale):
                return None
        if self._tips is None or self._frame_size is None:
            return None
        height, width = frame.shape[:2]
        if (width, height) != self._frame_size:
            self.reset()
            return None

        points: list[np.ndarray] = []
        for tracked_tip in self._tips:
            try:
                ok, box = tracked_tip.tracker.update(frame)
            except Exception:  # noqa: BLE001 - OpenCV backends expose platform-specific types.
                self.reset()
                return None
            if not ok:
                self.reset()
                return None
            x, y, box_width, box_height = box
            point = np.array(
                (
                    np.clip(x + box_width / 2, 0, width - 1),
                    np.clip(y + box_height / 2, 0, height - 1),
                ),
                dtype=np.float32,
            ) + tracked_tip.offset
            points.append(
                np.array(
                    (
                        np.clip(point[0], 0, width - 1),
                        np.clip(point[1], 0, height - 1),
                    ),
                    dtype=np.float32,
                )
            )

        if float(np.linalg.norm(points[0] - points[1])) > self._pinch_limit_pixels:
            self.reset()
            return None
        midpoint = (points[0] + points[1]) * 0.5
        return np.clip(
            midpoint / np.array((width - 1, height - 1), dtype=np.float32),
            0.0,
            1.0,
        )


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
