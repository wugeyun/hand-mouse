from dataclasses import replace
from types import SimpleNamespace

import numpy as np
import pytest

from hand_mouse import cli, tracker
from hand_mouse.cli import build_parser, strictly_increasing_timestamp
from hand_mouse.detectors import (
    HandPose,
    HorizontalThumbClickDetector,
    LeftPalmTiltScrollDetector,
    PeaceSignClickDetector,
)
from hand_mouse.pointer import POINTER_FINE, POINTER_IDLE, PalmPointerDetector


def test_timestamp_advances_when_frames_share_a_millisecond() -> None:
    assert strictly_increasing_timestamp(0, -1) == 0
    assert strictly_increasing_timestamp(0, 0) == 1
    assert strictly_increasing_timestamp(0, 1) == 2


def test_timestamp_catches_up_to_elapsed_time() -> None:
    assert strictly_increasing_timestamp(10, 2) == 10


def test_default_clicks_and_pointer_arm_at_300ms() -> None:
    args = build_parser().parse_args([])
    assert args.click_stable_time == args.pointer_stable_time == 0.3
    assert args.scroll_stable_time == 0.1
    for detector_class in (HorizontalThumbClickDetector, PeaceSignClickDetector):
        detector = detector_class()
        assert not detector.update(True, 0.0)
        assert not detector.update(True, 0.299)
        assert detector.update(True, 0.3)
        assert not detector.update(True, 0.4)
    detector = PalmPointerDetector()
    hand = open_hand()
    assert detector.update([hand], 0.0) == POINTER_IDLE
    assert detector.update([hand], 0.299) == POINTER_IDLE
    assert detector.update([hand], 0.3) == POINTER_FINE


def test_default_upright_hold_prepares_one_tilt_scroll(standing_hand) -> None:
    detector = LeftPalmTiltScrollDetector()
    assert detector.update([standing_hand()], 0) == 0
    assert detector.update([standing_hand()], 0.15) == 0
    assert detector.update([standing_hand()], 0.3) == 0
    assert detector.update([standing_hand(angle=35)], 0.4) == -1
    assert detector.update([standing_hand(angle=35)], 0.5) == 0


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


def open_hand(side="right") -> HandPose:
    points = np.zeros((21, 3), dtype=np.float32)
    points[0, :2] = (0.5, 0.8)
    points[[5, 9, 13, 17], :2] = ((0.35, 0.4), (0.45, 0.4), (0.55, 0.4), (0.65, 0.4))
    return HandPose(points, np.array((0.5, 0.6)), 0.4, finger_count=5, handedness=side)


def shifted(hand, dy):
    points = hand.points.copy()
    points[:, 1] += dy
    return replace(hand, points=points)


@pytest.fixture
def runtime(monkeypatch):
    import cv2

    state = SimpleNamespace(
        closed=0, released=0, overlay_closed=0, updates=[], lifecycle=[],
        opened=True, frames=[], poses=[], moves=[], scrolls=[], clicks=[], position=(960, 540), times=iter([0.0]),
    )

    class FakeTracker:
        def __init__(self, **kwargs):
            pass

        def close(self):
            state.lifecycle.append("tracker")
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
            state.lifecycle.append("camera")
            state.released += 1

    class FakeController:
        def __init__(self, **kwargs):
            self.live = kwargs["live"]

        def scroll(self, direction):
            state.scrolls.append(direction)

        def left_click(self):
            state.clicks.append("left")

        def right_click(self):
            state.clicks.append("right")

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
            state.lifecycle.append("overlay")
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
    hands = [open_hand() for _ in range(3)]
    hands[-1].points[:, 0] += 0.1
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


@pytest.mark.parametrize("stop", ["loss", "pinch", "partial", "left_fist", "right_fist"])
def test_pointer_stops_immediately_when_palm_closes_or_hand_is_lost(runtime, stop) -> None:
    hand = open_hand()
    stopping = {
        "loss": [],
        "pinch": [replace(hand, finger_count=2, pinch=True)],
        "partial": [replace(hand, finger_count=4)],
        "left_fist": [hand, replace(open_hand("left"), finger_count=0, fist=True)],
        "right_fist": [replace(hand, finger_count=0, fist=True)],
    }
    runtime.poses = [[hand], [hand], [hand], stopping[stop], []]
    runtime.frames = [np.zeros((100, 100, 3), dtype=np.uint8) for _ in runtime.poses]
    runtime.times = iter([0, 0.1, 0.41, 0.5, 0.6, 0.7])
    assert cli.main(["--no-preview"]) == 1
    assert len(runtime.moves) == 1
    assert runtime.scrolls == runtime.clicks == []


@pytest.mark.parametrize("side", ["left", "right"])
def test_grab_never_scrolls_and_stops_cursor(runtime, side) -> None:
    hand = open_hand(side)
    fist = replace(hand, finger_count=0, fist=True)
    runtime.poses = [[hand], [hand], [hand], [fist], [fist], [fist]]
    runtime.frames = [np.zeros((100, 100, 3), dtype=np.uint8) for _ in runtime.poses]
    runtime.times = iter([0, 0.1, 0.41, 0.7, 0.8, 0.9, 1.2])
    assert cli.main(["--no-preview"]) == 1
    assert runtime.scrolls == runtime.clicks == []
    assert len(runtime.moves) == (1 if side == "right" else 0)


@pytest.mark.parametrize("angle, direction", [(20, -1), (-20, 1)])
@pytest.mark.parametrize("with_right", [False, True])
def test_left_tilt_scrolls_once_with_no_return_or_cursor_conflicts(
    runtime, standing_hand, angle, direction, with_right,
) -> None:
    hands = [standing_hand(), standing_hand(), standing_hand(),
             standing_hand(angle=angle), standing_hand(angle=angle), standing_hand(), standing_hand(angle=-angle)]
    right = open_hand()
    runtime.poses = [
        [hand, shifted(right, index * 0.01)] if with_right else [hand]
        for index, hand in enumerate(hands)
    ]
    runtime.frames = [np.zeros((100, 100, 3), dtype=np.uint8) for _ in hands]
    runtime.times = iter([0, 0.1, 0.25, 0.41, 0.5, 0.6, 0.7, 0.75])
    assert cli.main(["--no-preview"]) == 1
    assert runtime.scrolls == [direction]
    assert runtime.clicks == []
    if with_right:
        assert runtime.moves and runtime.moves[-1][1] > 540
    else:
        assert runtime.moves == []


@pytest.mark.parametrize("side", ["left", "right"])
def test_fist_interrupts_left_tilt_without_scrolling(runtime, standing_hand, side) -> None:
    fist = standing_hand(tips=(), side=side)
    runtime.poses = [
        [standing_hand()], [standing_hand()], [standing_hand()],
        [fist] if side == "left" else [standing_hand(angle=35), fist], [standing_hand(angle=35)],
    ]
    runtime.frames = [np.zeros((100, 100, 3), dtype=np.uint8) for _ in runtime.poses]
    runtime.times = iter([0, 0.1, 0.25, 0.41, 0.5, 0.6])
    assert cli.main(["--no-preview"]) == 1
    assert runtime.scrolls == runtime.moves == runtime.clicks == []


@pytest.mark.parametrize("gesture, click", [("thumb_horizontal", "left"), ("peace_sign", "right")])
def test_click_gestures_keep_timing_and_do_not_trigger_scroll(runtime, gesture, click) -> None:
    hand = open_hand()
    clicking = replace(hand, finger_count=1, **{gesture: True})
    fist = replace(hand, finger_count=0, fist=True)
    runtime.poses = [[hand], [hand], [clicking], [clicking], [clicking], [fist]]
    runtime.frames = [np.zeros((100, 100, 3), dtype=np.uint8) for _ in runtime.poses]
    runtime.times = iter([0, 0.1, 0.7, 0.8, 1.11, 1.2, 1.3])
    assert cli.main(["--no-preview"]) == 1
    assert runtime.clicks == [click]
    assert runtime.scrolls == runtime.moves == []


def test_camera_releases_before_native_model_shutdown(runtime) -> None:
    assert cli.main(["--no-preview"]) == 1
    assert runtime.lifecycle == ["camera", "tracker"]


def test_all_resources_close_even_if_overlay_cleanup_fails(runtime, monkeypatch) -> None:
    from hand_mouse import overlay

    def fail_close(self):
        runtime.lifecycle.append("overlay")
        raise RuntimeError("overlay shutdown failed")

    monkeypatch.setattr(overlay.SkeletonOverlay, "close", fail_close)
    with pytest.raises(RuntimeError, match="overlay shutdown failed"):
        cli.main([])
    assert runtime.lifecycle == ["camera", "overlay", "tracker"]


@pytest.mark.parametrize("signal_name", ["SIGINT", "SIGTSTP", "SIGTERM", "SIGHUP"])
def test_macos_exit_signals_cleanup_and_restore_handlers(runtime, monkeypatch, signal_name) -> None:
    import signal

    if not all(hasattr(signal, name) for name in ("SIGINT", "SIGTSTP", "SIGHUP", "SIGTERM")):
        pytest.skip("Unix signal unavailable")
    from hand_mouse import overlay

    exit_signal = getattr(signal, signal_name)
    previous_handler = signal.getsignal(exit_signal)
    monkeypatch.setattr(cli.sys, "platform", "darwin")

    def trigger(self, *args):
        handler = signal.getsignal(exit_signal)
        assert callable(handler), "exit must clean up instead of suspending Python"
        handler(exit_signal, None)

    monkeypatch.setattr(overlay.SkeletonOverlay, "update", trigger)
    runtime.frames = [np.zeros((100, 100, 3), dtype=np.uint8)]
    runtime.poses = [[]]
    runtime.times = iter([0.0, 0.1])
    assert cli.main([]) == 0
    assert runtime.lifecycle == ["camera", "overlay", "tracker"]
    assert signal.getsignal(exit_signal) == previous_handler


@pytest.mark.parametrize("raise_error, expected_code", [(False, 0), (True, 1)])
def test_macos_native_shutdown_timeout_ends_only_the_child_process(tmp_path, raise_error, expected_code) -> None:
    import os
    import subprocess
    import sys
    from pathlib import Path

    marker = tmp_path / "camera-released.txt"
    script = """
import sys
import time
from pathlib import Path
from hand_mouse import cli
cli.sys.platform = 'darwin'
cli.NATIVE_SHUTDOWN_TIMEOUT = 0.15
with cli._runtime_resources() as resources:
    resources.callback(lambda: time.sleep(60))
    resources.callback(lambda: Path(sys.argv[1]).write_text('released'))
    if sys.argv[2] == 'error':
        raise RuntimeError('runtime failed before shutdown')
raise SystemExit('shutdown timeout failed to terminate the child')
"""
    result = subprocess.run(
        [sys.executable, "-u", "-c", script, str(marker), "error" if raise_error else "normal"],
        capture_output=True, text=True, timeout=10, check=False,
        env={**os.environ, "PYTHONPATH": str(Path(cli.__file__).resolve().parents[1])},
    )
    assert result.returncode == expected_code
    assert marker.read_text() == "released"
    assert "Shutdown timed out" in result.stderr
