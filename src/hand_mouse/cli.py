"""Command-line application for webcam gesture control."""

from __future__ import annotations

import argparse
import sys
import time
from typing import TYPE_CHECKING, Any, Optional, Sequence

from . import __version__
from .controller import InputController
from .pointer import CursorMapper, PointerModeDetector

if TYPE_CHECKING:
    from .detectors import HandPose


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Coarse webcam gesture controller for desktop applications")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("--camera", type=int, default=0, help="camera device index")
    parser.add_argument("--width", type=int, default=960)
    parser.add_argument("--height", type=int, default=540)
    parser.add_argument("--model", help="path to a MediaPipe hand_landmarker.task model")
    parser.add_argument("--live", action="store_true", help="send real mouse events; default is dry-run")
    parser.add_argument("--no-preview", action="store_true", help="do not open the camera preview window")
    parser.add_argument("--scroll-amount", type=int, default=5)
    parser.add_argument("--scroll-stable-time", type=float, default=1.0)
    parser.add_argument("--scroll-repeat-interval", type=float, default=0.25)
    parser.add_argument("--click-stable-time", type=float, default=0.5)
    parser.add_argument("--pointer-stable-time", type=float, default=0.5)
    parser.add_argument("--cursor-smoothing", type=float, default=0.35)
    parser.add_argument("--fine-sensitivity", type=float, default=0.35)
    return parser


def draw_status(
    frame: Any,
    hands: list["HandPose"],
    controller: InputController,
    action: str,
    pointer_mode: str,
) -> None:
    import cv2
    from .detectors import is_index_motion_ready, is_index_pointing, is_index_up

    mode = "LIVE" if controller.live else "DRY-RUN"
    if len(hands) == 1:
        if is_index_motion_ready(hands[0].points):
            index_state = "up" if is_index_up(hands[0].points) else "point"
        else:
            index_state = "folding" if is_index_pointing(hands[0].points) else "-"
    else:
        index_state = "-"
    left_fist = any(hand.handedness == "left" and hand.fist for hand in hands)
    cv2.putText(
        frame,
        f"MODE: {mode}  HANDS: {len(hands)}  HAND: {hands[0].handedness if len(hands) == 1 else '-'}  INDEX: {index_state}  THUMB SIDE: {hands[0].thumb_horizontal if len(hands) == 1 else '-'}",
        (20, 32),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (0, 220, 0),
        2,
    )
    cv2.putText(
        frame,
        f"LAST: {action or '-'}  POINTER: {pointer_mode}  LEFT FIST: {left_fist}",
        (20, 62),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.62,
        (0, 220, 220),
        2,
    )
    cv2.putText(
        frame,
        "right index: fine pointer | left fist: stop pointer",
        (20, 92),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.52,
        (220, 220, 220),
        1,
    )
    cv2.putText(
        frame,
        "right thumb side: left click | left palm: above | right palm: below",
        (20, 116),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.52,
        (220, 220, 220),
        1,
    )
    cv2.putText(
        frame,
        "Press q or ESC to quit",
        (20, frame.shape[0] - 20),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.52,
        (220, 220, 220),
        1,
    )


def run(args: argparse.Namespace) -> int:
    from .detectors import HorizontalThumbClickDetector, OpenPalmScrollDetector, is_index_motion_ready
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

    capture = cv2.VideoCapture(args.camera)
    capture.set(cv2.CAP_PROP_FRAME_WIDTH, args.width)
    capture.set(cv2.CAP_PROP_FRAME_HEIGHT, args.height)
    if not capture.isOpened():
        print(f"Cannot open camera {args.camera}", file=sys.stderr)
        tracker.close()
        return 1

    click_detector = HorizontalThumbClickDetector(stable_time=args.click_stable_time)
    scroll_detector = OpenPalmScrollDetector(
        stable_time=args.scroll_stable_time,
        repeat_interval=args.scroll_repeat_interval,
    )
    pointer_detector = PointerModeDetector(stable_time=args.pointer_stable_time)
    cursor_mapper = CursorMapper(
        controller.screen_size(),
        smoothing=args.cursor_smoothing,
        fine_sensitivity=args.fine_sensitivity,
    )
    last_action = ""

    start_time = time.monotonic()
    try:
        with tracker:
            while True:
                ok, frame = capture.read()
                if not ok:
                    print("Camera frame read failed", file=sys.stderr)
                    break

                frame = cv2.flip(frame, 1)
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                now = time.monotonic()
                result, poses = tracker.process(rgb, int((now - start_time) * 1000))
                pointer_mode = pointer_detector.update(poses, now)
                right_pose = next((pose for pose in poses if pose.handedness == "right"), None)
                if pointer_mode != cursor_mapper.mode:
                    cursor_mapper.set_mode(pointer_mode, right_pose, controller.position())
                motion_ready = right_pose is not None and is_index_motion_ready(right_pose.points)
                cursor_position = cursor_mapper.update(right_pose) if motion_ready else None
                if cursor_position is not None:
                    controller.move_cursor(cursor_position)

                if len(poses) == 1:
                    pose = poses[0]
                    click_pose = pose.handedness == "right" and pose.thumb_horizontal
                    if click_detector.update(click_pose, now):
                        controller.left_click()
                        last_action = "left click"
                    scroll_event = scroll_detector.update(pose.finger_count, pose.handedness, now)
                    if scroll_event:
                        controller.scroll(scroll_event)
                        last_action = "scroll up" if scroll_event > 0 else "scroll down"
                else:
                    click_detector.reset()
                    scroll_detector.reset()
                    if pointer_mode == "idle":
                        cursor_mapper.set_mode(pointer_mode, None, controller.position())

                if not args.no_preview:
                    tracker.draw_landmarks(frame, result)
                    draw_status(frame, poses, controller, last_action, pointer_mode)
                    cv2.imshow("hand-mouse", frame)
                    key = cv2.waitKey(1) & 0xFF
                    if key in (27, ord("q")):
                        break
                else:
                    time.sleep(0.001)
    except KeyboardInterrupt:
        pass
    finally:
        capture.release()
        cv2.destroyAllWindows()
    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    return run(build_parser().parse_args(argv))
