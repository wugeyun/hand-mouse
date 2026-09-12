"""Geometry and state detectors for coarse hand gestures."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

import numpy as np


def distance(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.linalg.norm(a[:2] - b[:2]))


def count_extended_fingers(points: np.ndarray) -> int:
    """Count extended fingers using coarse palm-relative distances."""
    wrist = points[0]
    count = 0
    for tip_index, pip_index in ((8, 6), (12, 10), (16, 14), (20, 18)):
        if distance(points[tip_index], wrist) > distance(points[pip_index], wrist) * 1.05:
            count += 1
    if distance(points[4], wrist) > distance(points[3], wrist) * 1.1:
        count += 1
    return count


def is_thumbs_up(points: np.ndarray) -> bool:
    """Return True for a thumb-up pose with the other fingers folded."""
    wrist = points[0]
    other_fingers_folded = all(
        distance(points[tip_index], wrist) < distance(points[pip_index], wrist) * 1.05
        for tip_index, pip_index in ((8, 6), (12, 10), (16, 14), (20, 18))
    )
    thumb_points_up = points[4, 1] < points[3, 1] < points[2, 1]
    thumb_is_extended = distance(points[4], wrist) > distance(points[3], wrist) * 1.05
    return other_fingers_folded and thumb_points_up and thumb_is_extended


@dataclass
class HandPose:
    points: np.ndarray
    center: np.ndarray
    box_scale: float
    finger_count: int = 0
    thumbs_up: bool = False
    handedness: Optional[str] = None


def make_pose(hand_landmarks, handedness: Optional[str] = None) -> HandPose:
    landmarks = getattr(hand_landmarks, "landmark", hand_landmarks)
    points = np.array(
        [[landmark.x, landmark.y, landmark.z] for landmark in landmarks],
        dtype=np.float32,
    )
    center = points[[0, 5, 9, 13, 17], :2].mean(axis=0)
    width = float(points[:, 0].max() - points[:, 0].min())
    height = float(points[:, 1].max() - points[:, 1].min())
    box_scale = max(math.sqrt(max(width * height, 0.0)), 1e-4)
    return HandPose(
        points=points,
        center=center,
        box_scale=box_scale,
        finger_count=count_extended_fingers(points),
        thumbs_up=is_thumbs_up(points),
        handedness=handedness,
    )


class ThumbUpClickDetector:
    """Emit one left click after a stable thumb-up state."""

    def __init__(self, stable_time: float = 0.5) -> None:
        self.stable_time = stable_time
        self.active = False
        self.candidate_since: Optional[float] = None

    def reset(self) -> None:
        self.active = False
        self.candidate_since = None

    def update(self, thumbs_up: bool, now: float) -> bool:
        if not thumbs_up:
            self.reset()
            return False
        if self.active:
            return False
        if self.candidate_since is None:
            self.candidate_since = now
            return False
        if now - self.candidate_since < self.stable_time:
            return False
        self.active = True
        return True


class OpenPalmScrollDetector:
    """Continuously scroll while a stable left or right open palm is held."""

    def __init__(self, stable_time: float = 1.0, repeat_interval: float = 0.25) -> None:
        self.stable_time = stable_time
        self.repeat_interval = repeat_interval
        self.active_hand: Optional[str] = None
        self.candidate_hand: Optional[str] = None
        self.candidate_since: Optional[float] = None
        self.last_scroll: Optional[float] = None

    def reset(self) -> None:
        self.active_hand = None
        self.candidate_hand = None
        self.candidate_since = None
        self.last_scroll = None

    def update(self, finger_count: int, handedness: Optional[str], now: float) -> int:
        if finger_count != 5 or handedness not in ("left", "right"):
            self.reset()
            return 0
        if self.active_hand == handedness:
            if self.last_scroll is not None and now - self.last_scroll >= self.repeat_interval:
                self.last_scroll = now
                return 1 if handedness == "left" else -1
            return 0
        if self.active_hand is not None and self.active_hand != handedness:
            self.reset()
        if self.candidate_hand != handedness:
            self.candidate_hand = handedness
            self.candidate_since = now
            return 0
        if self.candidate_since is None or now - self.candidate_since < self.stable_time:
            return 0
        self.active_hand = handedness
        self.last_scroll = now
        return 1 if handedness == "left" else -1
