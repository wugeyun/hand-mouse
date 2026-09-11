import numpy as np

from hand_mouse.controller import InputController
from hand_mouse.detectors import FistTapDetector, HandPose, SwipeDetector, ZoomDetector, is_fist


def pose(center: tuple[float, float], scale: float = 0.2, fist: bool = False) -> HandPose:
    points = np.zeros((21, 3), dtype=np.float32)
    return HandPose(points=points, center=np.array(center, dtype=np.float32), box_scale=scale, fist=fist)


def test_zoom_detector_maps_apart_and_together() -> None:
    detector = ZoomDetector(threshold=0.05, cooldown=0)
    hands = [pose((0.3, 0.5)), pose((0.7, 0.5))]
    assert detector.update(hands, 0.0) == 0
    assert detector.update([pose((0.2, 0.5)), pose((0.8, 0.5))], 0.1) == 1
    assert detector.update([pose((0.3, 0.5)), pose((0.7, 0.5))], 0.2) == -1


def test_swipe_detector_maps_up_and_down() -> None:
    detector = SwipeDetector(window=0.5, min_displacement=0.1, min_speed=0.1, cooldown=0)
    assert detector.update(np.array((0.5, 0.6)), 0.0) == 0
    assert detector.update(np.array((0.5, 0.5)), 0.1) == 0
    assert detector.update(np.array((0.5, 0.3)), 0.2) == 1
    detector.reset()
    assert detector.update(np.array((0.5, 0.3)), 1.0) == 0
    assert detector.update(np.array((0.5, 0.4)), 1.1) == 0
    assert detector.update(np.array((0.5, 0.6)), 1.2) == -1


def test_two_fist_pulses_resolve_to_left_click() -> None:
    detector = FistTapDetector(tap_window=0.5)

    def fist(scale: float) -> HandPose:
        return pose((0.5, 0.5), scale=scale, fist=True)

    detector.update(fist(1.0), 0.0)
    detector.update(fist(1.2), 0.1)
    detector.update(fist(1.0), 0.2)
    detector.update(fist(1.2), 0.3)
    detector.update(fist(1.0), 0.4)
    assert detector.tap_count == 2
    assert detector.update(None, 1.0) == ["left_click"]


def test_three_fist_pulses_resolve_to_right_click() -> None:
    detector = FistTapDetector(tap_window=0.5)

    def fist(scale: float) -> HandPose:
        return pose((0.5, 0.5), scale=scale, fist=True)

    detector.update(fist(1.0), 0.0)
    events = []
    for start, end in ((0.1, 0.2), (0.3, 0.4), (0.5, 0.6)):
        detector.update(fist(1.2), start)
        events = detector.update(fist(1.0), end)
    assert events == ["right_click"]


def test_is_fist_uses_coarse_finger_state() -> None:
    points = np.zeros((21, 3), dtype=np.float32)
    for tip, pip in ((8, 6), (12, 10), (16, 14), (20, 18)):
        points[pip, 0] = 2.0
        points[tip, 0] = 1.0
    assert is_fist(points)
    points[8, 0] = 3.0
    points[12, 0] = 3.0
    assert not is_fist(points)


def test_dry_run_controller_never_needs_to_send_input() -> None:
    controller = InputController(live=False, scroll_amount=1, zoom_amount=1, zoom_mode="wheel")
    controller.left_click()
    controller.right_click()
    controller.scroll(1)
    controller.zoom(-1)
