"""Command-line application for webcam gesture control."""

from __future__ import annotations

import argparse
import sys
import time
from typing import TYPE_CHECKING, Any, Optional, Sequence

from . import __version__
from .controller import InputController

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
    parser.add_argument("--click-stable-time", type=float, default=0.3)
    return parser


def draw_status(frame: Any, hands: list["HandPose"], controller: InputController, action: str) -> None:
    import cv2

    mode = "LIVE" if controller.live else "DRY-RUN"
    cv2.putText(
        frame,
        f"MODE: {mode}  HANDS: {len(hands)}  HAND: {hands[0].handedness if len(hands) == 1 else '-'}  FINGERS: {hands[0].finger_count if len(hands) == 1 else '-'}  THUMB UP: {hands[0].thumbs_up if len(hands) == 1 else '-'}",
        (20, 32),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (0, 220, 0),
        2,
    )
    cv2.putText(
        frame,
        f"LAST: {action or '-'}",
        (20, 62),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.62,
        (0, 220, 220),
        2,
    )
    cv2.putText(
        frame,
        "thumb up: left click | left palm: above | right palm: below",
        (20, 92),
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
    from .detectors import OpenPalmScrollDetector, ThumbUpClickDetector
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

    click_detector = ThumbUpClickDetector(stable_time=args.click_stable_time)
    scroll_detector = OpenPalmScrollDetector(
        stable_time=args.scroll_stable_time,
        repeat_interval=args.scroll_repeat_interval,
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

                if len(poses) == 1:
                    pose = poses[0]
                    if click_detector.update(pose.thumbs_up, now):
                        controller.left_click()
                        last_action = "left click"
                    scroll_event = scroll_detector.update(pose.finger_count, pose.handedness, now)
                    if scroll_event:
                        controller.scroll(scroll_event)
                        last_action = "scroll up" if scroll_event > 0 else "scroll down"
                else:
                    click_detector.reset()
                    scroll_detector.reset()

                if not args.no_preview:
                    tracker.draw_landmarks(frame, result)
                    draw_status(frame, poses, controller, last_action)
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
