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


def load_hands_backend():
    """Load the legacy Hands API explicitly across MediaPipe package layouts."""
    try:
        from mediapipe.python.solutions import drawing_utils, hands
    except ImportError:
        try:
            from mediapipe import solutions as mp_solutions
        except ImportError as exc:
            raise RuntimeError("MediaPipe Hands API is not available") from exc
        drawing_utils = mp_solutions.drawing_utils
        hands = mp_solutions.hands
    return drawing_utils, hands


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Coarse webcam gesture controller for desktop applications")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("--camera", type=int, default=0, help="camera device index")
    parser.add_argument("--width", type=int, default=960)
    parser.add_argument("--height", type=int, default=540)
    parser.add_argument("--live", action="store_true", help="send real mouse events; default is dry-run")
    parser.add_argument("--no-preview", action="store_true", help="do not open the camera preview window")
    parser.add_argument("--zoom-mode", choices=("wheel", "keys"), default="wheel", help="zoom mapping")
    parser.add_argument("--scroll-amount", type=int, default=5)
    parser.add_argument("--zoom-amount", type=int, default=2)
    parser.add_argument("--zoom-threshold", type=float, default=0.08)
    parser.add_argument("--swipe-distance", type=float, default=0.18)
    parser.add_argument("--swipe-speed", type=float, default=0.45)
    parser.add_argument("--pulse-threshold", type=float, default=0.14)
    parser.add_argument("--tap-window", type=float, default=0.75)
    return parser


def draw_status(frame: Any, hands: list["HandPose"], controller: InputController, action: str, tap_count: int) -> None:
    import cv2

    mode = "LIVE" if controller.live else "DRY-RUN"
    cv2.putText(
        frame,
        f"MODE: {mode}  HANDS: {len(hands)}",
        (20, 32),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (0, 220, 0),
        2,
    )
    cv2.putText(
        frame,
        f"LAST: {action or '-'}  FIST TAPS: {tap_count}",
        (20, 62),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.62,
        (0, 220, 220),
        2,
    )
    cv2.putText(
        frame,
        "2 hands: zoom | 1 hand wave: scroll | fist pulse x2/x3: click",
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
    from .detectors import FistTapDetector, SwipeDetector, ZoomDetector, make_pose

    try:
        import cv2
        drawing_utils, hands_module = load_hands_backend()
    except ImportError as exc:
        print(f"Missing dependency: {exc.name}. Install the project dependencies first.", file=sys.stderr)
        return 2
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        print("Use a MediaPipe build with the legacy Hands API or add a Tasks API backend.", file=sys.stderr)
        return 2

    try:
        controller = InputController(
            live=args.live,
            scroll_amount=args.scroll_amount,
            zoom_amount=args.zoom_amount,
            zoom_mode=args.zoom_mode,
        )
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    capture = cv2.VideoCapture(args.camera)
    capture.set(cv2.CAP_PROP_FRAME_WIDTH, args.width)
    capture.set(cv2.CAP_PROP_FRAME_HEIGHT, args.height)
    if not capture.isOpened():
        print(f"Cannot open camera {args.camera}", file=sys.stderr)
        return 1

    zoom_detector = ZoomDetector(threshold=args.zoom_threshold)
    swipe_detector = SwipeDetector(
        min_displacement=args.swipe_distance,
        min_speed=args.swipe_speed,
    )
    fist_detector = FistTapDetector(
        pulse_threshold=args.pulse_threshold,
        tap_window=args.tap_window,
    )
    last_action = ""

    def dispatch(event: str) -> None:
        nonlocal last_action
        if event == "left_click":
            controller.left_click()
            last_action = "left click"
        elif event == "right_click":
            controller.right_click()
            last_action = "right click"

    try:
        with hands_module.Hands(
            static_image_mode=False,
            max_num_hands=2,
            model_complexity=1,
            min_detection_confidence=0.6,
            min_tracking_confidence=0.6,
        ) as hands_model:
            while True:
                ok, frame = capture.read()
                if not ok:
                    print("Camera frame read failed", file=sys.stderr)
                    break

                frame = cv2.flip(frame, 1)
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                result = hands_model.process(rgb)
                poses = [make_pose(item) for item in (result.multi_hand_landmarks or [])]
                now = time.monotonic()

                if len(poses) == 2:
                    zoom_event = zoom_detector.update(poses, now)
                    swipe_detector.reset()
                    for event in fist_detector.update(None, now):
                        dispatch(event)
                    if zoom_event:
                        controller.zoom(zoom_event)
                        last_action = "zoom in" if zoom_event > 0 else "zoom out"
                elif len(poses) == 1:
                    zoom_detector.reset()
                    pose = poses[0]
                    if pose.fist:
                        swipe_detector.reset()
                        for event in fist_detector.update(pose, now):
                            dispatch(event)
                    else:
                        for event in fist_detector.update(None, now):
                            dispatch(event)
                        swipe_event = swipe_detector.update(pose.center, now)
                        if swipe_event:
                            controller.scroll(swipe_event)
                            last_action = "scroll up" if swipe_event > 0 else "scroll down"
                else:
                    zoom_detector.reset()
                    swipe_detector.reset()
                    for event in fist_detector.update(None, now):
                        dispatch(event)

                if not args.no_preview:
                    if result.multi_hand_landmarks:
                        for hand_landmarks in result.multi_hand_landmarks:
                            drawing_utils.draw_landmarks(
                                frame,
                                hand_landmarks,
                                hands_module.HAND_CONNECTIONS,
                            )
                    draw_status(frame, poses, controller, last_action, fist_detector.tap_count)
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
