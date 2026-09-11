"""Geometry and time-series detectors for coarse hand gestures."""

from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass
from typing import Optional

import numpy as np


def distance(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.linalg.norm(a[:2] - b[:2]))


def is_fist(points: np.ndarray) -> bool:
    """Return True when most non-thumb fingers are folded toward the palm."""
    wrist = points[0]
    folded = 0
    for tip_index, pip_index in ((8, 6), (12, 10), (16, 14), (20, 18)):
        if distance(points[tip_index], wrist) < distance(points[pip_index], wrist) * 1.05:
            folded += 1
    return folded >= 3


@dataclass
class HandPose:
    points: np.ndarray
    center: np.ndarray
    box_scale: float
    fist: bool


def make_pose(hand_landmarks) -> HandPose:
    points = np.array(
        [[landmark.x, landmark.y, landmark.z] for landmark in hand_landmarks.landmark],
        dtype=np.float32,
    )
    center = points[[0, 5, 9, 13, 17], :2].mean(axis=0)
    width = float(points[:, 0].max() - points[:, 0].min())
    height = float(points[:, 1].max() - points[:, 1].min())
    box_scale = max(math.sqrt(max(width * height, 0.0)), 1e-4)
    return HandPose(points, center, box_scale, is_fist(points))


class ZoomDetector:
    """Detect coarse changes in the distance between two hands."""

    def __init__(self, threshold: float = 0.08, cooldown: float = 0.18) -> None:
        self.threshold = threshold
        self.cooldown = cooldown
        self.anchor: Optional[float] = None
        self.last_event = 0.0

    def reset(self) -> None:
        self.anchor = None

    def update(self, hands: list[HandPose], now: float) -> int:
        if len(hands) != 2:
            self.reset()
            return 0

        current = distance(hands[0].center, hands[1].center)
        if self.anchor is None:
            self.anchor = current
            return 0

        if now - self.last_event < self.cooldown:
            return 0

        delta = current - self.anchor
        if delta >= self.threshold:
            self.anchor = current
            self.last_event = now
            return 1  # hands move apart: zoom in
        if delta <= -self.threshold:
            self.anchor = current
            self.last_event = now
            return -1  # hands move together: zoom out
        return 0


class SwipeDetector:
    """Detect one large vertical hand movement and emit one scroll event."""

    def __init__(
        self,
        window: float = 0.35,
        min_displacement: float = 0.18,
        min_speed: float = 0.45,
        cooldown: float = 0.45,
    ) -> None:
        self.window = window
        self.min_displacement = min_displacement
        self.min_speed = min_speed
        self.cooldown = cooldown
        self.samples: deque[tuple[float, float]] = deque()
        self.last_event = 0.0

    def reset(self) -> None:
        self.samples.clear()

    def update(self, center: np.ndarray, now: float) -> int:
        self.samples.append((now, float(center[1])))
        while self.samples and now - self.samples[0][0] > self.window:
            self.samples.popleft()

        if now - self.last_event < self.cooldown or len(self.samples) < 3:
            return 0

        start_time, start_y = self.samples[0]
        displacement = float(center[1]) - start_y
        duration = max(now - start_time, 1e-3)
        if abs(displacement) < self.min_displacement:
            return 0
        if abs(displacement) / duration < self.min_speed:
            return 0

        self.last_event = now
        self.samples.clear()
        return 1 if displacement < 0 else -1  # hand up/down -> scroll up/down


class FistTapDetector:
    """Count forward/backward fist pulses as a double or triple tap."""

    def __init__(
        self,
        pulse_threshold: float = 0.14,
        release_threshold: float = 0.045,
        tap_window: float = 0.75,
        min_interval: float = 0.12,
    ) -> None:
        self.pulse_threshold = pulse_threshold
        self.release_threshold = release_threshold
        self.tap_window = tap_window
        self.min_interval = min_interval
        self.baseline: Optional[float] = None
        self.in_pulse = False
        self.tap_count = 0
        self.last_tap: Optional[float] = None

    def reset(self) -> None:
        self.baseline = None
        self.in_pulse = False
        self.tap_count = 0
        self.last_tap = None

    def _resolve_expired(self, now: float) -> Optional[str]:
        if self.last_tap is None or now - self.last_tap <= self.tap_window:
            return None
        action = "left_click" if self.tap_count == 2 else None
        self.reset()
        return action

    def update(self, pose: Optional[HandPose], now: float) -> list[str]:
        actions: list[str] = []
        if pose is None or not pose.fist:
            expired = self._resolve_expired(now)
            if expired:
                actions.append(expired)
            if self.tap_count == 0:
                self.baseline = None
                self.in_pulse = False
            return actions

        expired = self._resolve_expired(now)
        if expired:
            actions.append(expired)

        scale = pose.box_scale
        if self.baseline is None:
            self.baseline = scale
            return actions

        if not self.in_pulse:
            if self.tap_count == 0 or scale < self.baseline * (1.0 + self.pulse_threshold * 0.5):
                self.baseline = self.baseline * 0.94 + scale * 0.06
            if scale > self.baseline * (1.0 + self.pulse_threshold):
                self.in_pulse = True
        elif scale <= self.baseline * (1.0 + self.release_threshold):
            if self.last_tap is None or now - self.last_tap >= self.min_interval:
                self.tap_count += 1
                self.last_tap = now
                if self.tap_count >= 3:
                    actions.append("right_click")
                    self.reset()
                else:
                    self.in_pulse = False
                    self.baseline = scale
        return actions
