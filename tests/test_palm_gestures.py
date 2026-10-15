from dataclasses import replace

import numpy as np

from hand_mouse.detectors import HandPose, index_base_point
from hand_mouse.pointer import POINTER_FINE, POINTER_IDLE, PalmPointerDetector


def open_hand(side="right"):
    points = np.zeros((21, 3), dtype=np.float32)
    points[0, :2] = (0.5, 0.8)
    points[[5, 9, 13, 17], :2] = ((0.35, 0.4), (0.45, 0.4), (0.55, 0.4), (0.65, 0.4))
    return HandPose(points, np.array((0.5, 0.6)), 0.4, finger_count=5, handedness=side)


def test_control_point_is_index_base_and_follows_hand_rotation():
    hand = open_hand()
    assert np.allclose(index_base_point(hand.points), (0.35, 0.4))
    hand.points[[4, 8, 12, 16, 20], :2] = 100
    assert np.allclose(index_base_point(hand.points), (0.35, 0.4))
    hand.points[[0, 9, 13, 17], :2] = 0.9
    assert np.allclose(index_base_point(hand.points), (0.35, 0.4))
    hand.points[:, :2] = hand.points[:, :2] @ np.array(((0, 1), (-1, 0))) + (1, 0)
    assert np.allclose(index_base_point(hand.points), (0.6, 0.35))


def test_right_open_palm_arms_pointer_and_partial_close_or_loss_stops_it():
    detector = PalmPointerDetector()
    hand = open_hand()
    assert detector.update([hand], 0) == POINTER_IDLE
    assert detector.update([hand], 0.299) == POINTER_IDLE
    assert detector.update([hand], 0.3) == POINTER_FINE
    assert detector.update([replace(hand, finger_count=4)], 0.4) == POINTER_IDLE
    assert detector.update([hand], 0.5) == POINTER_IDLE
    assert detector.update([hand], 0.81) == POINTER_FINE
    assert detector.update([], 0.9) == POINTER_IDLE
    assert detector.update([open_hand("left")], 1) == POINTER_IDLE
