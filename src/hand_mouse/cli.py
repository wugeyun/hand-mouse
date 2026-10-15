"""Command-line application for webcam gesture control."""

from __future__ import annotations

import argparse
import math
import os
import select
import signal
import sys
import time
from collections.abc import Callable, Sequence
from contextlib import ExitStack, contextmanager
from threading import Event, Thread, Timer

from . import __version__
from .controller import InputController
from .pointer import POINTER_FINE, POINTER_IDLE, CursorMapper, PalmPointerDetector

NATIVE_SHUTDOWN_TIMEOUT = 5.0


def _force_runtime_exit(exit_code: int) -> None:
    try:
        os.write(2, b"Shutdown timed out; terminating this camera application.\n")
    finally:
        # Native MediaPipe worker threads can block Python's interpreter exit.
        # This terminates only this process; its camera resources are released.
        os._exit(exit_code)


@contextmanager
def _runtime_resources():
    resources = ExitStack()
    exit_code = 0
    try:
        yield resources
    except KeyboardInterrupt:
        raise
    except BaseException:
        exit_code = 1
        raise
    finally:
        timer = None
        if sys.platform == "darwin":
            timer = Timer(NATIVE_SHUTDOWN_TIMEOUT, _force_runtime_exit, args=(exit_code,))
            timer.daemon = True
            timer.start()
        try:
            resources.close()
        finally:
            if timer is not None:
                timer.cancel()


def strictly_increasing_timestamp(elapsed_ms: int, previous_timestamp_ms: int) -> int:
    """Return a MediaPipe-compatible timestamp even for sub-millisecond frames."""
    return max(elapsed_ms, previous_timestamp_ms + 1)


def nonnegative_int(value: str) -> int:
    number = int(value)
    if number < 0:
        raise argparse.ArgumentTypeError("must be a nonnegative integer")
    return number


def positive_int(value: str) -> int:
    number = nonnegative_int(value)
    if number == 0:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return number


def nonnegative_float(value: str) -> float:
    number = float(value)
    if not math.isfinite(number) or number < 0:
        raise argparse.ArgumentTypeError("must be a finite nonnegative number")
    return number


def positive_float(value: str) -> float:
    number = nonnegative_float(value)
    if number == 0:
        raise argparse.ArgumentTypeError("must be a finite positive number")
    return number


def smoothing_fraction(value: str) -> float:
    number = positive_float(value)
    if number > 1:
        raise argparse.ArgumentTypeError("must be greater than 0 and at most 1")
    return number


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Coarse webcam gesture controller for desktop applications")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("--camera", type=nonnegative_int, default=0, help="camera device index")
    parser.add_argument("--width", type=positive_int, default=960)
    parser.add_argument("--height", type=positive_int, default=540)
    parser.add_argument("--model", help="path to a MediaPipe hand_landmarker.task model")
    parser.add_argument("--live", action="store_true", help="send real mouse events; default is dry-run")
    parser.add_argument("--no-preview", action="store_true", help="hide the desktop skeleton overlay")
    parser.add_argument("--scroll-amount", type=positive_int, default=5)
    parser.add_argument(
        "--scroll-stable-time", type=nonnegative_float, default=0.1,
        help="upright left-palm hold duration before each tilt can scroll",
    )
    parser.add_argument(
        "--scroll-repeat-interval", type=positive_float, default=0.25,
        help="legacy option; tilt scrolling emits once until the palm returns upright",
    )
    parser.add_argument("--click-stable-time", type=nonnegative_float, default=0.3)
    parser.add_argument(
        "--pointer-stable-time",
        "--pinch-stable-time",
        dest="pointer_stable_time",
        type=nonnegative_float,
        default=0.3,
        help="stable right open-palm duration before mouse movement starts",
    )
    parser.add_argument("--cursor-smoothing", type=smoothing_fraction, default=0.35)
    parser.add_argument("--fine-sensitivity", type=positive_float, default=0.35)
    parser.add_argument("--cursor-max-gain", type=positive_float, default=3.0)
    parser.add_argument("--cursor-acceleration-speed", type=positive_float, default=1.0)
    parser.add_argument("--cursor-deadzone", type=nonnegative_float, default=0.0015)
    return parser


def run(args: argparse.Namespace, should_exit: Callable[[], bool] | None = None) -> int:
    from .detectors import (
        HorizontalThumbClickDetector,
        LeftPalmTiltScrollDetector,
        PeaceSignClickDetector,
        index_base_point,
        is_emergency_fist,
    )
    from .tracker import MediaPipeHandTracker

    try:
        import cv2
    except ImportError as exc:
        print(f"Missing dependency: {exc.name}. Install the project dependencies first.", file=sys.stderr)
        return 2

    try:
        controller = InputController(
            live=args.live,
            scroll_amount=args.scroll_amount,
        )
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    try:
        tracker = MediaPipeHandTracker(model_path=args.model)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    capture = None
    overlay = None
    try:
        with _runtime_resources() as resources:
            resources.enter_context(tracker)
            # LIFO: camera first, then overlay, then the native model.
            resources.callback(lambda: overlay.close() if overlay is not None else None)
            if should_exit is not None and should_exit():
                return 0
            capture = cv2.VideoCapture(args.camera)
            resources.callback(capture.release)
            capture.set(cv2.CAP_PROP_FRAME_WIDTH, args.width)
            capture.set(cv2.CAP_PROP_FRAME_HEIGHT, args.height)
            if not capture.isOpened():
                print(f"Cannot open camera {args.camera}", file=sys.stderr)
                return 1

            click_detector = HorizontalThumbClickDetector(stable_time=args.click_stable_time)
            right_click_detector = PeaceSignClickDetector(stable_time=args.click_stable_time)
            scroll_detector = LeftPalmTiltScrollDetector(stable_time=args.scroll_stable_time)
            pointer_detector = PalmPointerDetector(stable_time=args.pointer_stable_time)
            initial_position = controller.position()
            cursor_mapper = CursorMapper(
                controller.display_for_position(initial_position),
                smoothing=args.cursor_smoothing,
                fine_sensitivity=args.fine_sensitivity,
                max_gain=args.cursor_max_gain,
                acceleration_speed=args.cursor_acceleration_speed,
                deadzone=args.cursor_deadzone,
            )
            if not args.no_preview:
                try:
                    from .overlay import SkeletonOverlay

                    overlay = SkeletonOverlay(live=args.live)
                except (ImportError, RuntimeError) as exc:
                    print(f"Cannot start desktop skeleton overlay: {exc}", file=sys.stderr)
                    return 2

            start_time = time.monotonic()
            last_timestamp_ms = -1
            while should_exit is None or not should_exit():
                ok, frame = capture.read()
                if should_exit is not None and should_exit():
                    break
                if not ok:
                    print("Camera frame read failed", file=sys.stderr)
                    return 1

                frame = cv2.flip(frame, 1)
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                now = time.monotonic()
                timestamp_ms = strictly_increasing_timestamp(
                    int((now - start_time) * 1000),
                    last_timestamp_ms,
                )
                last_timestamp_ms = timestamp_ms
                _result, poses = tracker.process(rgb, timestamp_ms)
                if should_exit is not None and should_exit():
                    break
                fist_stop = any(is_emergency_fist(hand) for hand in poses)
                scroll_event = 0
                if fist_stop:
                    pointer_detector.reset()
                    click_detector.reset()
                    right_click_detector.reset()
                    scroll_detector.reset()
                    pointer_mode = POINTER_IDLE
                    if cursor_mapper.mode != POINTER_IDLE:
                        screen_position = controller.position()
                        cursor_mapper.set_mode(
                            POINTER_IDLE,
                            None,
                            screen_position,
                            now,
                            controller.display_for_position(screen_position),
                        )
                    cursor_position = None
                else:
                    scroll_event = scroll_detector.update(poses, now, frame_aspect_ratio=frame.shape[1] / frame.shape[0])
                    pointer_mode = pointer_detector.update(poses, now)
                    right_pose = next((pose for pose in poses if pose.handedness == "right"), None)
                    control_point = (
                        index_base_point(right_pose.points)
                        if pointer_mode == POINTER_FINE and right_pose is not None else None
                    )
                    if pointer_mode != cursor_mapper.mode:
                        screen_position = controller.position()
                        cursor_mapper.set_mode(
                            pointer_mode,
                            control_point,
                            screen_position,
                            now,
                            controller.display_for_position(screen_position),
                        )
                    cursor_position = cursor_mapper.update(control_point, now)
                if cursor_position is not None:
                    controller.move_cursor(cursor_position)

                if not fist_stop and len(poses) == 1:
                    pose = poses[0]
                    click_pose = pose.handedness == "right" and pose.thumb_horizontal and not pose.pinch
                    if click_detector.update(click_pose, now):
                        controller.left_click()
                    right_click_pose = pose.handedness == "right" and pose.peace_sign
                    if right_click_detector.update(right_click_pose, now):
                        controller.right_click()
                else:
                    click_detector.reset()
                    right_click_detector.reset()

                if scroll_event:
                    controller.scroll(scroll_event)

                if overlay is not None:
                    overlay.update(poses, controller.position(), cursor_mapper.display)
                else:
                    time.sleep(0.001)
    except KeyboardInterrupt:
        pass
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    previous_handlers = {}
    exit_requested = False
    monitor_stop = Event()
    monitor = None
    terminal_fds = tuple(fd for fd in (0, 1, 2) if os.isatty(fd)) if sys.platform == "darwin" else ()
    terminal_poller = select.poll() if terminal_fds else None
    if terminal_poller is not None:
        for fd in terminal_fds:
            terminal_poller.register(fd, select.POLLHUP | select.POLLERR | select.POLLNVAL)

    def request_exit(signum, frame) -> None:
        nonlocal exit_requested
        # Qt/native callbacks can swallow exceptions raised from a signal handler.
        exit_requested = True

    def should_exit() -> bool:
        return exit_requested

    def watch_exit() -> None:
        deadline = None
        while not monitor_stop.wait(0.1):
            if (
                any(not os.isatty(fd) for fd in terminal_fds)
                or (terminal_poller is not None and terminal_poller.poll(0))
            ):
                request_exit(None, None)
            if exit_requested:
                now = time.monotonic()
                if deadline is None:
                    deadline = now + NATIVE_SHUTDOWN_TIMEOUT
                elif now >= deadline:
                    _force_runtime_exit(0)

    try:
        if sys.platform == "darwin":
            for exit_signal in (signal.SIGINT, signal.SIGTSTP, signal.SIGHUP, signal.SIGTERM):
                previous_handlers[exit_signal] = signal.signal(exit_signal, request_exit)
            monitor = Thread(target=watch_exit, name="hand-mouse-exit-watchdog", daemon=True)
            monitor.start()
        return run(args, should_exit=should_exit)
    except KeyboardInterrupt:
        return 0
    finally:
        monitor_stop.set()
        if monitor is not None:
            monitor.join(timeout=0.2)
        for exit_signal, previous_handler in previous_handlers.items():
            signal.signal(exit_signal, previous_handler)
