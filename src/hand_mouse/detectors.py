"""Geometry and state detectors for coarse hand gestures."""

from __future__ import annotations

import math
from dataclasses import dataclass

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


def is_peace_sign(points: np.ndarray, box_scale: float, separation_ratio: float = 0.25) -> bool:
    """Return True for a V sign: index and middle extended, ring and pinky folded."""
    wrist = points[0]
    index_extended = (
        distance(points[8], wrist) > distance(points[6], wrist) * 1.05
        and finger_straightness(points, 5, 6, 8) >= 0.75
    )
    middle_extended = (
        distance(points[12], wrist) > distance(points[10], wrist) * 1.05
        and finger_straightness(points, 9, 10, 12) >= 0.75
    )
    folded_back = all(
        distance(points[tip_index], wrist) < distance(points[pip_index], wrist) * 1.35
        and finger_straightness(points, mcp_index, pip_index, tip_index) < 0.75
        for mcp_index, pip_index, tip_index in ((13, 14, 16), (17, 18, 20))
    )
    separated = distance(points[8], points[12]) >= max(box_scale, 1e-4) * separation_ratio
    return index_extended and middle_extended and folded_back and separated


def is_thumb_index_pinch(points: np.ndarray, box_scale: float, threshold: float = 0.45) -> bool:
    """Return True when the thumb and index fingertips are close relative to the hand."""
    wrist = points[0]
    index_reaches_out = distance(points[8], wrist) > distance(points[6], wrist) * 1.02
    thumb_reaches_out = distance(points[4], wrist) > distance(points[3], wrist) * 1.02
    fingertips_touch = distance(points[4], points[8]) <= max(box_scale, 1e-4) * threshold
    return index_reaches_out and thumb_reaches_out and fingertips_touch


def pinch_point(points: np.ndarray) -> np.ndarray:
    """Return the normalized midpoint between the thumb and index fingertips."""
    return (points[4, :2] + points[8, :2]) * 0.5


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
    pinch: bool = False
    peace_sign: bool = False
    handedness: str | None = None


def extended_finger_tips(points: np.ndarray) -> tuple[int, ...]:
    """Return clearly extended long fingertips, regardless of finger identity."""
    wrist = points[0]
    return tuple(
        tip for mcp, pip, tip in ((5, 6, 8), (9, 10, 12), (13, 14, 16), (17, 18, 20))
        if distance(points[tip], wrist) > distance(points[pip], wrist) * 1.05
        and finger_straightness(points, mcp, pip, tip) >= 0.75
    )


def is_emergency_fist(hand: HandPose) -> bool:
    """Return True for a fist that is not another explicit hand gesture."""
    return hand.fist and not hand.pinch and not hand.thumb_horizontal


def make_pose(hand_landmarks, handedness: str | None = None) -> HandPose:
    landmarks = getattr(hand_landmarks, "landmark", hand_landmarks)
    points = np.array(
        [[landmark.x, landmark.y, landmark.z] for landmark in landmarks],
        dtype=np.float32,
    )
    center = points[[0, 5, 9, 13, 17], :2].mean(axis=0)
    width = float(points[:, 0].max() - points[:, 0].min())
    height = float(points[:, 1].max() - points[:, 1].min())
    box_scale = max(math.sqrt(max(width * height, 0.0)), 1e-4)
    pinch = is_thumb_index_pinch(points, box_scale)
    peace_sign = is_peace_sign(points, box_scale)
    return HandPose(
        points=points,
        center=center,
        box_scale=box_scale,
        finger_count=count_extended_fingers(points),
        thumb_horizontal=is_horizontal_thumb(points),
        fist=is_fist(points),
        pinch=pinch,
        peace_sign=peace_sign,
        handedness=handedness,
    )


class HorizontalThumbClickDetector:
    """Emit one left click after a stable horizontal-thumb state."""

    def __init__(self, stable_time: float = 0.3) -> None:
        self.stable_time = stable_time
        self.active = False
        self.candidate_since: float | None = None

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


class PeaceSignClickDetector:
    """Emit one right click after a stable right-hand V sign."""

    def __init__(self, stable_time: float = 0.3) -> None:
        self.stable_time = stable_time
        self.active = False
        self.candidate_since: float | None = None

    def reset(self) -> None:
        self.active = False
        self.candidate_since = None

    def update(self, peace_sign: bool, now: float) -> bool:
        if not peace_sign:
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


def is_open_palm(hand: HandPose) -> bool:
    """Require five extended fingers without an overlapping click or pinch."""
    return (
        hand.finger_count == 5
        and not hand.fist
        and not hand.pinch
        and not hand.thumb_horizontal
        and not hand.peace_sign
    )


def palm_control_point(points: np.ndarray) -> np.ndarray:
    """Use a point inside the palm, three quarters from wrist to knuckles."""
    return points[0, :2] * 0.25 + points[[5, 9, 13, 17], :2].mean(axis=0) * 0.75


class LeftPalmTiltScrollDetector:
    """Scroll once on a left palm tilt, then require a deliberate upright hold."""

    def __init__(self, stable_time: float = 0.1) -> None:
        self.stable_time = stable_time
        self.neutral_since: float | None = None
        self.last_seen: float | None = None
        self.armed = False

    def reset(self) -> None:
        self.neutral_since = None
        self.last_seen = None
        self.armed = False

    def update(self, hands: list[HandPose], now: float, frame_aspect_ratio: float = 1.0) -> int:
        if any(is_emergency_fist(hand) for hand in hands):
            self.reset()
            return 0
        left = next((hand for hand in hands if hand.handedness == "left"), None)
        if self.last_seen is not None and now - self.last_seen > 0.2:
            self.reset()
        if left is None or len(extended_finger_tips(left.points)) < 3:
            return 0
        axis = left.points[9, :2] - left.points[0, :2]
        if float(np.linalg.norm(axis)) < 0.03:
            return 0
        tilt = math.degrees(math.atan2(float(axis[0]) * frame_aspect_ratio, -float(axis[1])))
        if abs(tilt) > 70:
            return 0
        self.last_seen = now
        if abs(tilt) <= 12:
            if self.neutral_since is None:
                self.neutral_since = now
            if now - self.neutral_since + 1e-9 >= self.stable_time:
                self.armed = True
            return 0
        self.neutral_since = None
        if self.armed and abs(tilt) + 1e-5 >= 20:
            self.armed = False
            return -1 if tilt > 0 else 1
        return 0
