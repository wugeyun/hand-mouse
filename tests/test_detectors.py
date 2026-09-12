import numpy as np

from hand_mouse.controller import DisplayBounds, InputController, select_display
from hand_mouse.detectors import (
    HandPose,
    HorizontalThumbClickDetector,
    OpenPalmScrollDetector,
    PeaceSignClickDetector,
    count_extended_fingers,
    is_emergency_fist,
    is_fist,
    is_horizontal_thumb,
    is_index_motion_ready,
    is_index_pointing,
    is_peace_sign,
    is_thumb_index_pinch,
    pinch_point,
)
from hand_mouse.pointer import (
    POINTER_FINE,
    POINTER_IDLE,
    CursorMapper,
    PinchPointerDetector,
    PinchPointTracker,
)


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


def pinching_pose(handedness: str) -> HandPose:
    hand = pointing_pose(handedness)
    hand.points[4, :2] = hand.points[8, :2]
    return hand


def peace_pose(handedness: str) -> HandPose:
    points = np.zeros((21, 3), dtype=np.float32)
    points[0] = (0.50, 0.80, 0.0)
    points[5] = (0.43, 0.70, 0.0)
    points[6] = (0.42, 0.58, 0.0)
    points[8] = (0.38, 0.22, 0.0)
    points[9] = (0.55, 0.70, 0.0)
    points[10] = (0.57, 0.56, 0.0)
    points[12] = (0.64, 0.18, 0.0)
    points[13] = (0.66, 0.70, 0.0)
    points[14] = (0.66, 0.75, 0.0)
    points[16] = (0.58, 0.72, 0.0)
    points[17] = (0.73, 0.72, 0.0)
    points[18] = (0.73, 0.78, 0.0)
    points[20] = (0.66, 0.74, 0.0)
    points[3] = (0.42, 0.78, 0.0)
    points[4] = (0.34, 0.72, 0.0)
    return HandPose(
        points=points,
        center=np.array((0.5, 0.5), dtype=np.float32),
        box_scale=0.4,
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


def test_right_pinch_arms_fine_pointer_and_release_stops_it() -> None:
    detector = PinchPointerDetector(stable_time=0.5)
    right = pinching_pose("right")
    released = pointing_pose("right")
    assert is_thumb_index_pinch(right.points, right.box_scale)
    assert np.allclose(pinch_point(right.points), right.points[4, :2])
    assert detector.update([right], 0.0) == POINTER_IDLE
    assert detector.update([right], 0.4) == POINTER_IDLE
    assert detector.update([right], 0.5) == POINTER_FINE
    assert detector.update([released], 0.6) == POINTER_IDLE
    assert detector.update([right], 1.0) == POINTER_IDLE
    assert detector.update([right], 1.5) == POINTER_FINE
    assert detector.update([], 1.7) == POINTER_FINE


def test_right_peace_sign_emits_one_right_click_until_released() -> None:
    detector = PeaceSignClickDetector(stable_time=0.5)
    peace = peace_pose("right")
    assert is_peace_sign(peace.points, peace.box_scale)
    assert not detector.update(True, 0.0)
    assert not detector.update(True, 0.4)
    assert detector.update(True, 0.5)
    assert not detector.update(True, 0.6)
    assert not detector.update(False, 0.7)
    assert not detector.update(True, 1.2)
    assert detector.update(True, 1.7)


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
    slow_mapper.set_mode(POINTER_FINE, base.points[8, :2], (500, 500), 0.0)
    slow = pointing_pose("right")
    slow.points[8, :2] = (0.51, 0.5)
    slow_position = slow_mapper.update(slow.points[8, :2], 0.1)

    fast_mapper = CursorMapper(
        (1000, 1000),
        smoothing=1.0,
        fine_sensitivity=0.2,
        max_gain=2.0,
        acceleration_speed=1.0,
        deadzone=0.0,
    )
    fast_mapper.set_mode(POINTER_FINE, base.points[8, :2], (500, 500), 0.0)
    fast = pointing_pose("right")
    fast.points[8, :2] = (0.51, 0.5)
    fast_position = fast_mapper.update(fast.points[8, :2], 0.01)

    assert slow_position is not None
    assert fast_position is not None
    assert fast_position[0] - 500 > (slow_position[0] - 500) * 4


def test_cursor_mapper_maps_camera_edges_to_the_active_display() -> None:
    display = DisplayBounds(100, -50, 1000, 800)
    base = pointing_pose("right")
    base.points[8, :2] = (0.25, 0.25)
    mapper = CursorMapper(
        display,
        smoothing=1.0,
        fine_sensitivity=1.0,
        max_gain=1.0,
        deadzone=0.0,
        transition_duration=0.1,
    )
    mapper.set_mode(POINTER_FINE, base.points[8, :2], (600, 300), 0.0)

    top_left = pointing_pose("right")
    top_left.points[8, :2] = (0.0, 0.0)
    first_position = mapper.update(top_left.points[8, :2], 0.01)
    assert first_position is not None
    assert first_position[0] > display.x
    assert first_position[1] > display.y

    assert mapper.update(top_left.points[8, :2], 0.11) == (display.x, display.y)

    bottom_right = pointing_pose("right")
    bottom_right.points[8, :2] = (1.0, 1.0)
    assert mapper.update(bottom_right.points[8, :2], 0.21) == (
        display.x + display.width - 1,
        display.y + display.height - 1,
    )


def test_select_display_uses_the_display_containing_the_cursor() -> None:
    left = DisplayBounds(0, 0, 1000, 800, is_primary=True)
    right = DisplayBounds(1000, 100, 1200, 900)

    assert select_display((100, 100), (left, right)) == left
    assert select_display((1100, 200), (left, right)) == right
    assert select_display((1000, 50), (left, right)) == left


def test_any_fist_is_an_emergency_stop_but_a_pinch_is_not() -> None:
    left_fist = fist_pose("left")
    pinching = pinching_pose("right")
    pinching.fist = True
    pinching.pinch = True
    horizontal_thumb = fist_pose("right")
    horizontal_thumb.thumb_horizontal = True

    assert is_fist(left_fist.points)
    assert is_emergency_fist(left_fist)
    assert not is_emergency_fist(pinching)
    assert not is_emergency_fist(horizontal_thumb)


def test_open_palm_scroll_is_suppressed_while_pinching() -> None:
    detector = OpenPalmScrollDetector(stable_time=1.0, repeat_interval=0.25)

    assert detector.update(5, "right", 0.0, pinch=True) == 0
    assert detector.update(5, "right", 1.0, pinch=True) == 0
    assert detector.update(5, "right", 1.1, pinch=False) == 0


def test_local_pinch_tracker_returns_the_moving_midpoint(monkeypatch) -> None:
    class FakeTracker:
        def __init__(self) -> None:
            self.box = None

        def init(self, _frame, box) -> bool:
            self.box = box
            return True

        def update(self, frame):
            shift = float(frame[0, 0, 0])
            x, y, width, height = self.box
            return True, (x + shift, y, width, height)

    monkeypatch.setattr(PinchPointTracker, "_create_tracker", staticmethod(FakeTracker))
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    points = np.zeros((21, 3), dtype=np.float32)
    points[4, :2] = (0.40, 0.50)
    points[8, :2] = (0.45, 0.50)
    tracker = PinchPointTracker()

    assert tracker.start(frame, points, box_scale=0.2)
    frame[0, 0, 0] = 5
    midpoint = tracker.update(frame)

    assert midpoint is not None
    assert np.allclose(midpoint, (0.425 + 5 / 99, 0.5), atol=0.01)


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
    controller.right_click()
    controller.scroll(1)
