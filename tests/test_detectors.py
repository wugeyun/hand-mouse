import numpy as np

from hand_mouse.controller import InputController
from hand_mouse.detectors import (
    HandPose,
    HorizontalThumbClickDetector,
    OpenPalmScrollDetector,
    count_extended_fingers,
    is_fist,
    is_horizontal_thumb,
    is_index_motion_ready,
    is_index_pointing,
)
from hand_mouse.pointer import POINTER_FINE, POINTER_IDLE, CursorMapper, PointerModeDetector


def pose(center: tuple[float, float], scale: float = 0.2, finger_count: int = 0) -> HandPose:
    points = np.zeros((21, 3), dtype=np.float32)
    return HandPose(
        points=points,
        center=np.array(center, dtype=np.float32),
        box_scale=scale,
        finger_count=finger_count,
    )


def pointing_pose(handedness: str) -> HandPose:
    points = np.zeros((21, 3), dtype=np.float32)
    points[0, 1] = 0.5
    points[5, 1] = 0.45
    points[6, 1] = 0.4
    points[7, 1] = 0.25
    points[8, 1] = 0.1
    for pip, tip in ((10, 12), (14, 16), (18, 20)):
        points[pip] = (0.2, 0.45, 0.0)
        points[tip] = (0.1, 0.46, 0.0)
    points[3] = (0.15, 0.45, 0.0)
    points[4] = (0.1, 0.46, 0.0)
    return HandPose(
        points=points,
        center=np.array((0.5, 0.5), dtype=np.float32),
        box_scale=0.2,
        finger_count=1,
        handedness=handedness,
    )


def fist_pose(handedness: str) -> HandPose:
    points = np.zeros((21, 3), dtype=np.float32)
    points[0] = (0.1, 0.5, 0.0)
    for mcp, pip, tip in ((5, 6, 8), (9, 10, 12), (13, 14, 16), (17, 18, 20)):
        points[mcp] = (0.1, 0.4, 0.0)
        points[pip] = (0.1, 0.3, 0.0)
        points[tip] = (0.1, 0.45, 0.0)
    return HandPose(
        points=points,
        center=np.array((0.5, 0.5), dtype=np.float32),
        box_scale=0.2,
        fist=True,
        handedness=handedness,
    )


def test_open_palms_map_left_and_right_hands_to_fixed_scroll_directions() -> None:
    detector = OpenPalmScrollDetector(stable_time=1.0, repeat_interval=0.25)
    assert detector.update(5, "left", 0.0) == 0
    assert detector.update(5, "left", 0.9) == 0
    assert detector.update(5, "left", 1.0) == 1
    assert detector.update(5, "left", 1.1) == 0
    assert detector.update(5, "left", 1.25) == 1
    assert detector.update(4, "left", 1.4) == 0
    assert detector.update(5, "right", 1.5) == 0
    assert detector.update(5, "right", 2.5) == -1


def test_horizontal_thumb_state_emits_one_left_click_until_released() -> None:
    detector = HorizontalThumbClickDetector(stable_time=0.5)
    assert not detector.update(True, 0.0)
    assert not detector.update(True, 0.4)
    assert detector.update(True, 0.5)
    assert not detector.update(True, 0.6)
    assert not detector.update(False, 0.7)
    assert not detector.update(True, 0.8)
    assert detector.update(True, 1.3)


def test_right_index_arms_fine_pointer_and_left_fist_stops_it() -> None:
    detector = PointerModeDetector(stable_time=0.5)
    right = pointing_pose("right")
    left_fist = fist_pose("left")
    assert detector.update([right], 0.0) == POINTER_IDLE
    assert detector.update([right], 0.4) == POINTER_IDLE
    assert detector.update([right], 0.5) == POINTER_FINE
    assert is_fist(left_fist.points)
    assert detector.update([right, left_fist], 0.6) == POINTER_IDLE
    assert detector.update([right, left_fist], 1.0) == POINTER_IDLE
    assert detector.update([right], 1.1) == POINTER_IDLE
    assert detector.update([right], 1.6) == POINTER_FINE
    assert detector.update([], 1.7) == POINTER_IDLE


def test_cursor_acceleration_moves_farther_for_faster_motion() -> None:
    base = pointing_pose("right")
    base.points[8, :2] = (0.5, 0.5)

    slow_mapper = CursorMapper(
        (1000, 1000),
        smoothing=1.0,
        fine_sensitivity=0.2,
        max_gain=2.0,
        acceleration_speed=1.0,
        deadzone=0.0,
    )
    slow_mapper.set_mode(POINTER_FINE, base, (500, 500), 0.0)
    slow = pointing_pose("right")
    slow.points[8, :2] = (0.51, 0.5)
    slow_position = slow_mapper.update(slow, 0.1)

    fast_mapper = CursorMapper(
        (1000, 1000),
        smoothing=1.0,
        fine_sensitivity=0.2,
        max_gain=2.0,
        acceleration_speed=1.0,
        deadzone=0.0,
    )
    fast_mapper.set_mode(POINTER_FINE, base, (500, 500), 0.0)
    fast = pointing_pose("right")
    fast.points[8, :2] = (0.51, 0.5)
    fast_position = fast_mapper.update(fast, 0.01)

    assert slow_position is not None
    assert fast_position is not None
    assert fast_position[0] - 500 > (slow_position[0] - 500) * 4


def test_count_extended_fingers_distinguishes_four_and_five() -> None:
    points = np.zeros((21, 3), dtype=np.float32)
    for tip, pip in ((8, 6), (12, 10), (16, 14), (20, 18)):
        points[pip, 0] = 2.0
        points[tip, 0] = 3.0
    points[3, 0] = 2.0
    points[4, 0] = 1.0
    assert count_extended_fingers(points) == 4
    points[4, 0] = 3.0
    assert count_extended_fingers(points) == 5


def test_horizontal_thumb_pose_is_detected_and_distinct() -> None:
    points = np.zeros((21, 3), dtype=np.float32)
    for tip, pip in ((8, 6), (12, 10), (16, 14), (20, 18)):
        points[pip, 0] = 2.0
        points[tip, 0] = 1.0
    points[3] = (0.2, 0.0, 0.0)
    points[4] = (0.5, 0.0, 0.0)
    assert is_horizontal_thumb(points)
    points[4] = (0.2, -0.5, 0.0)
    assert not is_horizontal_thumb(points)


def test_index_pointing_requires_one_straight_long_finger() -> None:
    points = np.zeros((21, 3), dtype=np.float32)
    points[0, 1] = 0.5
    points[5, 1] = 0.45
    points[6, 1] = 0.4
    points[7, 1] = 0.25
    points[8, 1] = 0.1
    for pip, tip in ((10, 12), (14, 16), (18, 20)):
        points[pip] = (0.2, 0.45, 0.0)
        points[tip] = (0.1, 0.46, 0.0)
    points[3] = (0.15, 0.5, 0.0)
    points[4] = (0.1, 0.5, 0.0)
    assert is_index_pointing(points)
    points[4] = (0.5, 0.5, 0.0)
    assert is_index_pointing(points)


def test_cursor_motion_freezes_when_index_starts_folding() -> None:
    hand = pointing_pose("right")
    assert is_index_motion_ready(hand.points)
    hand.points[8] = (0.2, 0.35, 0.0)
    assert not is_index_motion_ready(hand.points)


def test_open_palm_does_not_enter_index_pointer_mode() -> None:
    points = np.zeros((21, 3), dtype=np.float32)
    points[0, 1] = 0.5
    for mcp, pip, tip in ((5, 6, 8), (9, 10, 12), (13, 14, 16), (17, 18, 20)):
        points[mcp] = (0.2, 0.45, 0.0)
        points[pip] = (0.2, 0.3, 0.0)
        points[tip] = (0.2, 0.05, 0.0)
    points[3] = (0.2, 0.1, 0.0)
    points[4] = (0.3, 0.0, 0.0)
    assert not is_index_pointing(points)


def test_dry_run_controller_never_needs_to_send_input() -> None:
    controller = InputController(live=False, scroll_amount=1)
    controller.left_click()
    controller.scroll(1)
