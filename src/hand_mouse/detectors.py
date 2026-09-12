"""Geometry and state detectors for coarse hand gestures."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

import numpy as np


def distance(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.linalg.norm(a[:2] - b[:2]))


def finger_straightness(points: np.ndarray, mcp_index: int, pip_index: int, tip_index: int) -> float:
    first_segment = points[pip_index] - points[mcp_index]
    second_segment = points[tip_index] - points[pip_index]
    denominator = float(np.linalg.norm(first_segment) * np.linalg.norm(second_segment))
    if denominator <= 1e-6:
        return -1.0
    return float(np.dot(first_segment, second_segment) / denominator)


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


def is_horizontal_thumb(points: np.ndarray) -> bool:
    """Return True for a sideways thumb with the other fingers folded."""
    wrist = points[0]
    other_fingers_folded = all(
        distance(points[tip_index], wrist) < distance(points[pip_index], wrist) * 1.35
        and finger_straightness(points, mcp_index, pip_index, tip_index) < 0.75
        for mcp_index, pip_index, tip_index in ((5, 6, 8), (9, 10, 12), (13, 14, 16), (17, 18, 20))
    )
    thumb_vector = points[4, :2] - points[3, :2]
    thumb_is_horizontal = abs(float(thumb_vector[0])) > abs(float(thumb_vector[1])) * 1.5
    thumb_is_extended = distance(points[4], wrist) > distance(points[3], wrist) * 1.05
    return other_fingers_folded and thumb_is_horizontal and thumb_is_extended


def is_fist(points: np.ndarray) -> bool:
    """Return True when at least three long fingers are clearly folded."""
    wrist = points[0]
    folded = 0
    for mcp_index, pip_index, tip_index in ((5, 6, 8), (9, 10, 12), (13, 14, 16), (17, 18, 20)):
        tip_near_palm = distance(points[tip_index], wrist) < distance(points[pip_index], wrist) * 1.35
        finger_bent = finger_straightness(points, mcp_index, pip_index, tip_index) < 0.75
        if tip_near_palm and finger_bent:
            folded += 1
    return folded >= 3


def is_index_pointing(points: np.ndarray) -> bool:
    """Return True for one straight index with the other long fingers folded."""
    wrist = points[0]
    index_extended = distance(points[8], wrist) > distance(points[6], wrist) * 1.02
    index_straight = finger_straightness(points, 5, 6, 8) >= 0.75
    other_fingers_folded = all(
        distance(points[tip_index], wrist) < distance(points[pip_index], wrist) * 1.35
        and finger_straightness(points, mcp_index, pip_index, tip_index) < 0.75
        for mcp_index, pip_index, tip_index in ((9, 10, 12), (13, 14, 16), (17, 18, 20))
    )
    return index_extended and index_straight and other_fingers_folded and not is_horizontal_thumb(points)


def is_index_up(points: np.ndarray) -> bool:
    """Return True when the pointing index finger is initially directed upward."""
    return is_index_pointing(points) and points[8, 1] < points[6, 1] - 0.015


def is_index_motion_ready(points: np.ndarray, min_straightness: float = 0.85) -> bool:
    """Allow cursor updates only while the index finger remains straight."""
    if not is_index_pointing(points):
        return False
    middle_segment = points[7] - points[6]
    distal_segment = points[8] - points[7]
    denominator = float(np.linalg.norm(middle_segment) * np.linalg.norm(distal_segment))
    if denominator <= 1e-6:
        return False
    straightness = float(np.dot(middle_segment, distal_segment) / denominator)
    return straightness >= min_straightness


@dataclass
class HandPose:
    points: np.ndarray
    center: np.ndarray
    box_scale: float
    finger_count: int = 0
    thumb_horizontal: bool = False
    fist: bool = False
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
        thumb_horizontal=is_horizontal_thumb(points),
        fist=is_fist(points),
        handedness=handedness,
    )


class HorizontalThumbClickDetector:
    """Emit one left click after a stable horizontal-thumb state."""

    def __init__(self, stable_time: float = 0.5) -> None:
        self.stable_time = stable_time
        self.active = False
        self.candidate_since: Optional[float] = None

    def reset(self) -> None:
        self.active = False
        self.candidate_since = None

    def update(self, thumb_horizontal: bool, now: float) -> bool:
        if not thumb_horizontal:
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
