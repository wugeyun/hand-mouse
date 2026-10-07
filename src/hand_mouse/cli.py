"""Command-line application for webcam gesture control."""

from __future__ import annotations

import argparse
import math
import sys
import time
from collections.abc import Sequence

from . import __version__
from .controller import InputController
from .pointer import POINTER_FINE, POINTER_IDLE, CursorMapper, PinchPointerDetector, PinchPointTracker


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
    parser.add_argument("--scroll-stable-time", type=nonnegative_float, default=0.5)
    parser.add_argument("--scroll-repeat-interval", type=positive_float, default=0.25)
    parser.add_argument("--click-stable-time", type=nonnegative_float, default=0.3)
    parser.add_argument(
        "--pointer-stable-time",
        "--pinch-stable-time",
        dest="pointer_stable_time",
        type=nonnegative_float,
        default=0.3,
        help="stable thumb-index pinch duration before mouse movement starts",
    )
    parser.add_argument("--cursor-smoothing", type=smoothing_fraction, default=0.35)
    parser.add_argument("--fine-sensitivity", type=positive_float, default=0.35)
    parser.add_argument("--cursor-max-gain", type=positive_float, default=3.0)
    parser.add_argument("--cursor-acceleration-speed", type=positive_float, default=1.0)
    parser.add_argument("--cursor-deadzone", type=nonnegative_float, default=0.0015)
    return parser


def run(args: argparse.Namespace) -> int:
    from .detectors import (
        HorizontalThumbClickDetector,
        OpenPalmScrollDetector,
        PeaceSignClickDetector,
        is_emergency_fist,
        is_thumb_index_pinch,
        pinch_point,
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
        with tracker:
            capture = cv2.VideoCapture(args.camera)
            capture.set(cv2.CAP_PROP_FRAME_WIDTH, args.width)
            capture.set(cv2.CAP_PROP_FRAME_HEIGHT, args.height)
            if not capture.isOpened():
                print(f"Cannot open camera {args.camera}", file=sys.stderr)
                return 1

            click_detector = HorizontalThumbClickDetector(stable_time=args.click_stable_time)
            right_click_detector = PeaceSignClickDetector(stable_time=args.click_stable_time)
            scroll_detector = OpenPalmScrollDetector(
                stable_time=args.scroll_stable_time,
                repeat_interval=args.scroll_repeat_interval,
            )
            pointer_detector = PinchPointerDetector(stable_time=args.pointer_stable_time)
            pinch_tracker = PinchPointTracker()
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
            while True:
                ok, frame = capture.read()
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
                fist_stop = any(is_emergency_fist(hand) for hand in poses)
                if fist_stop:
                    pointer_detector.reset()
                    pinch_tracker.reset()
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
                    pointer_mode = pointer_detector.update(poses, now)
                    right_pose = next((pose for pose in poses if pose.handedness == "right"), None)
                    right_pinching = right_pose is not None and is_thumb_index_pinch(
                        right_pose.points,
                        right_pose.box_scale,
                    )
                    if pointer_mode != cursor_mapper.mode:
                        screen_position = controller.position()
                        control_point = pinch_point(right_pose.points) if right_pinching else None
                        cursor_mapper.set_mode(
                            pointer_mode,
                            control_point,
                            screen_position,
                            now,
                            controller.display_for_position(screen_position),
                        )
                        if pointer_mode != POINTER_FINE:
                            pinch_tracker.reset()

                    control_point = None
                    if pointer_mode == POINTER_FINE:
                        if right_pinching:
                            control_point = pinch_point(right_pose.points)
                            pinch_tracker.remember(frame, right_pose.points, right_pose.box_scale)
                        elif pinch_tracker.active:
                            control_point = pinch_tracker.update(frame)
                        if control_point is None:
                            pointer_detector.reset()
                            pinch_tracker.reset()
                            pointer_mode = POINTER_IDLE
                            screen_position = controller.position()
                            cursor_mapper.set_mode(
                                POINTER_IDLE,
                                None,
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
                    scroll_event = scroll_detector.update(
                        pose.finger_count,
                        pose.handedness,
                        now,
                        pinch=pose.pinch,
                    )
                    if scroll_event:
                        controller.scroll(scroll_event)
                else:
                    click_detector.reset()
                    right_click_detector.reset()
                    scroll_detector.reset()

                if overlay is not None:
                    overlay.update(poses, controller.position(), cursor_mapper.display)
                else:
                    time.sleep(0.001)
    except KeyboardInterrupt:
        pass
    finally:
        if capture is not None:
            capture.release()
        if overlay is not None:
            overlay.close()
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    return run(build_parser().parse_args(argv))
