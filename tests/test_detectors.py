import numpy as np

from hand_mouse.controller import InputController
from hand_mouse.detectors import HandPose, OpenPalmScrollDetector, ThumbUpClickDetector, count_extended_fingers, is_thumbs_up


def pose(center: tuple[float, float], scale: float = 0.2, finger_count: int = 0) -> HandPose:
    points = np.zeros((21, 3), dtype=np.float32)
    return HandPose(
        points=points,
        center=np.array(center, dtype=np.float32),
        box_scale=scale,
        finger_count=finger_count,
    )


def test_open_palms_map_left_and_right_hands_to_fixed_scroll_directions() -> None:
    detector = OpenPalmScrollDetector(stable_time=0.5)
    assert detector.update(5, "left", 0.0) == 0
    assert detector.update(5, "left", 0.4) == 0
    assert detector.update(5, "left", 0.5) == 1
    assert detector.update(5, "left", 0.6) == 0
    assert detector.update(4, "left", 0.7) == 0
    assert detector.update(5, "right", 0.8) == 0
    assert detector.update(5, "right", 1.3) == -1


def test_thumb_up_state_emits_one_left_click_until_released() -> None:
    detector = ThumbUpClickDetector(stable_time=0.5)
    assert not detector.update(True, 0.0)
    assert not detector.update(True, 0.4)
    assert detector.update(True, 0.5)
    assert not detector.update(True, 0.6)
    assert not detector.update(False, 0.7)
    assert not detector.update(True, 0.8)
    assert detector.update(True, 1.3)


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


def test_thumb_up_pose_is_coarse_and_distinct() -> None:
    points = np.zeros((21, 3), dtype=np.float32)
    for tip, pip in ((8, 6), (12, 10), (16, 14), (20, 18)):
        points[pip, 0] = 2.0
        points[tip, 0] = 1.0
    points[2, 1] = 0.4
    points[3, 1] = 0.3
    points[4, 1] = -0.5
    assert is_thumbs_up(points)
    points[4, 1] = 0.5
    assert not is_thumbs_up(points)


def test_dry_run_controller_never_needs_to_send_input() -> None:
    controller = InputController(live=False, scroll_amount=1)
    controller.left_click()
    controller.scroll(1)
