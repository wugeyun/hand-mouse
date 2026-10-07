from types import SimpleNamespace

import numpy as np
import pytest

from hand_mouse import cli, tracker
from hand_mouse.cli import build_parser, strictly_increasing_timestamp
from hand_mouse.detectors import HandPose, HorizontalThumbClickDetector, OpenPalmScrollDetector, PeaceSignClickDetector
from hand_mouse.pointer import POINTER_FINE, POINTER_IDLE, PinchPointerDetector


def test_timestamp_advances_when_frames_share_a_millisecond() -> None:
    assert strictly_increasing_timestamp(0, -1) == 0
    assert strictly_increasing_timestamp(0, 0) == 1
    assert strictly_increasing_timestamp(0, 1) == 2


def test_timestamp_catches_up_to_elapsed_time() -> None:
    assert strictly_increasing_timestamp(10, 2) == 10


def test_default_clicks_and_pointer_arm_at_300ms() -> None:
    args = build_parser().parse_args([])
    assert args.click_stable_time == args.pointer_stable_time == 0.3
    assert args.scroll_stable_time == 0.5
    for detector_class in (HorizontalThumbClickDetector, PeaceSignClickDetector):
        detector = detector_class()
        assert not detector.update(True, 0.0)
        assert not detector.update(True, 0.299)
        assert detector.update(True, 0.3)
        assert not detector.update(True, 0.4)
    detector = PinchPointerDetector()
    hand = pinching_hand()
    assert detector.update([hand], 0.0) == POINTER_IDLE
    assert detector.update([hand], 0.299) == POINTER_IDLE
    assert detector.update([hand], 0.3) == POINTER_FINE


def test_default_scroll_starts_at_500ms_and_repeats_every_250ms() -> None:
    detector = OpenPalmScrollDetector()
    assert detector.update(5, "left", 0.0) == 0
    assert detector.update(5, "left", 0.499) == 0
    assert detector.update(5, "left", 0.5) == 1
    assert detector.update(5, "left", 0.749) == 0
    assert detector.update(5, "left", 0.75) == 1


@pytest.mark.parametrize("option, value", [
    ("--width", "0"), ("--height", "-1"), ("--camera", "-1"),
    ("--scroll-amount", "0"), ("--scroll-repeat-interval", "-1"),
    ("--click-stable-time", "nan"), ("--pinch-stable-time", "inf"),
    ("--scroll-stable-time", "-0.1"), ("--cursor-smoothing", "nan"),
    ("--cursor-smoothing", "0"), ("--cursor-smoothing", "1.1"),
    ("--fine-sensitivity", "0"), ("--cursor-max-gain", "-1"),
    ("--cursor-acceleration-speed", "0"), ("--cursor-deadzone", "-1"),
])
def test_invalid_parameters_are_rejected_before_startup(option, value) -> None:
    with pytest.raises(SystemExit) as exc:
        build_parser().parse_args([option, value])
    assert exc.value.code == 2


def pinching_hand() -> HandPose:
    points = np.zeros((21, 3), dtype=np.float32)
    points[0, :2] = (0.5, 0.8)
    points[3, :2] = (0.4, 0.6)
    points[6, :2] = (0.5, 0.6)
    points[4, :2] = points[8, :2] = (0.5, 0.3)
    return HandPose(points, np.array((0.5, 0.5)), 0.2, pinch=True, handedness="right")


@pytest.fixture
def runtime(monkeypatch):
    import cv2

    state = SimpleNamespace(
        closed=0, released=0, overlay_closed=0, updates=[],
        opened=True, frames=[], poses=[], moves=[], position=(960, 540), times=iter([0.0]),
    )

    class FakeTracker:
        def __init__(self, **kwargs):
            pass

        def close(self):
            state.closed += 1

        def __enter__(self):
            return self

        def __exit__(self, *args):
            self.close()

        def process(self, frame, timestamp):
            return None, state.poses.pop(0)

    class FakeCapture:
        def __init__(self, *args):
            pass

        def set(self, *args):
            pass

        def isOpened(self):
            return state.opened

        def read(self):
            if state.frames:
                return True, state.frames.pop(0)
            return False, None

        def release(self):
            state.released += 1

    class FakeController:
        def __init__(self, **kwargs):
            self.live = kwargs["live"]

        def position(self):
            return state.position

        def display_for_position(self, position):
            return 1920, 1080

        def move_cursor(self, position):
            state.moves.append(position)
            state.position = position

    from hand_mouse import overlay

    class FakeOverlay:
        def __init__(self, live=False):
            pass

        def update(self, hands, cursor_position=None, display=None):
            state.updates.append((hands, cursor_position, display))

        def close(self):
            state.overlay_closed += 1

    def unexpected_camera_window(*args):
        pytest.fail("the desktop overlay must not open or draw a camera window")

    monkeypatch.setattr(cli, "InputController", FakeController)
    monkeypatch.setattr(tracker, "MediaPipeHandTracker", FakeTracker)
    monkeypatch.setattr(cv2, "VideoCapture", FakeCapture)
    monkeypatch.setattr(overlay, "SkeletonOverlay", FakeOverlay)
    monkeypatch.setattr(cv2, "imshow", unexpected_camera_window)
    monkeypatch.setattr(cv2, "putText", unexpected_camera_window)
    monkeypatch.setattr(cv2, "circle", unexpected_camera_window)
    monkeypatch.setattr(cli.time, "monotonic", lambda: next(state.times))
    monkeypatch.setattr(cli.time, "sleep", lambda duration: None)
    state.controller_class = FakeController
    return state


def test_camera_read_failure_returns_failure_and_releases_resources(runtime) -> None:
    assert cli.main(["--no-preview"]) == 1
    assert (runtime.closed, runtime.released, runtime.overlay_closed) == (1, 1, 0)


def test_camera_open_failure_releases_resources(runtime) -> None:
    runtime.opened = False
    assert cli.main(["--no-preview"]) == 1
    assert (runtime.closed, runtime.released) == (1, 1)


def test_startup_failure_releases_resources(runtime, monkeypatch) -> None:
    def fail(self):
        raise RuntimeError("display lookup failed")

    monkeypatch.setattr(runtime.controller_class, "position", fail)
    with pytest.raises(RuntimeError, match="display lookup failed"):
        cli.main(["--no-preview"])
    assert (runtime.closed, runtime.released, runtime.overlay_closed) == (1, 1, 0)


def test_default_output_is_only_desktop_skeleton_and_resources_close(runtime) -> None:
    runtime.frames = [np.zeros((100, 100, 3), dtype=np.uint8)]
    runtime.poses = [[]]
    runtime.times = iter([0.0, 0.1])
    assert cli.main([]) == 1
    assert len(runtime.updates) == 1
    assert (runtime.closed, runtime.released, runtime.overlay_closed) == (1, 1, 1)


def test_no_preview_disables_the_desktop_overlay(runtime) -> None:
    runtime.frames = [np.zeros((100, 100, 3), dtype=np.uint8)]
    runtime.poses = [[]]
    runtime.times = iter([0.0, 0.1])
    assert cli.main(["--no-preview"]) == 1
    assert runtime.updates == []
    assert runtime.overlay_closed == 0


def test_overlay_receives_current_cursor_after_movement(runtime) -> None:
    hands = [pinching_hand() for _ in range(3)]
    hands[-1].points[[4, 8], 0] += 0.1
    runtime.frames = [np.zeros((100, 100, 3), dtype=np.uint8) for _ in hands]
    runtime.poses = [[hand] for hand in hands]
    runtime.times = iter([0.0, 0.1, 0.4, 0.5])
    assert cli.main([]) == 1
    assert runtime.moves
    assert runtime.updates[-1][1] == runtime.moves[-1]


def test_overlay_closes_on_keyboard_interrupt(runtime, monkeypatch) -> None:
    from hand_mouse import overlay

    def interrupt(*args):
        raise KeyboardInterrupt

    monkeypatch.setattr(overlay.SkeletonOverlay, "update", interrupt)
    runtime.frames = [np.zeros((100, 100, 3), dtype=np.uint8)]
    runtime.poses = [[]]
    runtime.times = iter([0.0, 0.1])
    assert cli.main([]) == 0
    assert (runtime.closed, runtime.released, runtime.overlay_closed) == (1, 1, 1)


def test_overlay_startup_failure_releases_camera_and_tracker(runtime, monkeypatch) -> None:
    from hand_mouse import overlay

    def fail(*args, **kwargs):
        raise RuntimeError("no desktop screen is available")

    monkeypatch.setattr(overlay.SkeletonOverlay, "__init__", fail)
    assert cli.main([]) == 2
    assert (runtime.closed, runtime.released, runtime.overlay_closed) == (1, 1, 0)


def test_reliable_pinch_skips_local_tracking_and_loss_uses_fallback(runtime, monkeypatch) -> None:
    calls = []

    class FakeTracker:
        def init(self, frame, box):
            self.box = box
            calls.append("init")
            return True

        def update(self, frame):
            calls.append("update")
            return True, self.box

    monkeypatch.setattr(cli.PinchPointTracker, "_create_tracker", staticmethod(FakeTracker))
    hand = pinching_hand()
    runtime.frames = [np.zeros((100, 100, 3), dtype=np.uint8) for _ in range(4)]
    runtime.poses = [[hand], [hand], [hand], []]
    runtime.times = iter([0.0, 0.1, 0.4, 0.5, 0.6])
    assert cli.main(["--no-preview"]) == 1
    assert calls == ["init", "init", "update", "update"]
    # The activation frame preserves the existing cursor; later frames move it.
    assert len(runtime.moves) == 2


def test_fist_and_pinch_release_cancel_pending_fallback(runtime, monkeypatch) -> None:
    hand = pinching_hand()
    fist = HandPose(np.zeros((21, 3)), np.array((0.5, 0.5)), 0.2, fist=True, handedness="left")

    def unexpected_tracker():
        pytest.fail("a stopped pointer must not start local tracking")

    monkeypatch.setattr(cli.PinchPointTracker, "_create_tracker", staticmethod(unexpected_tracker))
    released = HandPose(np.zeros((21, 3)), np.array((0.5, 0.5)), 0.2, handedness="right")
    runtime.frames = [np.zeros((100, 100, 3), dtype=np.uint8) for _ in range(8)]
    runtime.poses = [[hand], [hand], [fist], [], [hand], [hand], [released], []]
    runtime.times = iter([0.0, 0.1, 0.4, 0.5, 0.6, 0.7, 1.1, 1.2, 1.3])
    assert cli.main(["--no-preview"]) == 1
    assert runtime.moves == []
