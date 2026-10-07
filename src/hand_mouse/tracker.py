"""MediaPipe Tasks hand tracking and model management."""

from __future__ import annotations

import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

import numpy as np

from .detectors import make_pose

MODEL_URL = "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task"
BUNDLED_MODEL_PATH = Path(__file__).resolve().parent / "models" / "hand_landmarker.task"
DEFAULT_MODEL_PATH = Path.home() / ".cache" / "hand-mouse" / "hand_landmarker.task"
MIN_MODEL_SIZE = 100_000


def resolve_model_path(model_path: str | None) -> Path:
    if model_path:
        path = Path(model_path).expanduser()
        if not path.is_file():
            raise RuntimeError(f"MediaPipe model file does not exist: {path}")
        return path

    if BUNDLED_MODEL_PATH.is_file() and BUNDLED_MODEL_PATH.stat().st_size >= MIN_MODEL_SIZE:
        return BUNDLED_MODEL_PATH

    path = DEFAULT_MODEL_PATH
    if path.is_file() and path.stat().st_size > 0:
        return path

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(".download")
    print(f"Downloading MediaPipe hand model to {path}", file=sys.stderr)
    try:
        with urllib.request.urlopen(MODEL_URL, timeout=90) as response, temporary_path.open("wb") as output:
            while chunk := response.read(1024 * 1024):
                output.write(chunk)
        if temporary_path.stat().st_size < MIN_MODEL_SIZE:
            raise RuntimeError("downloaded MediaPipe model is unexpectedly small")
        os.replace(temporary_path, path)
    except (OSError, urllib.error.URLError, RuntimeError) as exc:
        temporary_path.unlink(missing_ok=True)
        raise RuntimeError(
            "could not download the MediaPipe hand model; download it manually and pass --model PATH"
        ) from exc
    return path


class MediaPipeHandTracker:
    """Track up to two hands using the current MediaPipe Tasks API."""

    def __init__(
        self,
        model_path: str | None = None,
        min_detection_confidence: float = 0.6,
        min_presence_confidence: float = 0.6,
        min_tracking_confidence: float = 0.6,
    ) -> None:
        try:
            import mediapipe as mp
            from mediapipe.tasks import python
            from mediapipe.tasks.python import vision
        except ImportError as exc:
            raise RuntimeError("MediaPipe Tasks API is required; install the project dependencies first") from exc

        model = resolve_model_path(model_path)
        options = vision.HandLandmarkerOptions(
            base_options=python.BaseOptions(model_asset_path=str(model)),
            running_mode=vision.RunningMode.VIDEO,
            num_hands=2,
            min_hand_detection_confidence=min_detection_confidence,
            min_hand_presence_confidence=min_presence_confidence,
            min_tracking_confidence=min_tracking_confidence,
        )
        try:
            self._landmarker = vision.HandLandmarker.create_from_options(options)
        except Exception as exc:
            raise RuntimeError(f"could not initialize MediaPipe hand tracker: {exc}") from exc

        self._mp = mp
        self._connections = vision.HandLandmarksConnections.HAND_CONNECTIONS

    def process(self, frame_rgb: np.ndarray, timestamp_ms: int):
        image = self._mp.Image(image_format=self._mp.ImageFormat.SRGB, data=frame_rgb)
        result = self._landmarker.detect_for_video(image, timestamp_ms)
        handedness = []
        for categories in getattr(result, "handedness", []):
            category = categories[0] if categories else None
            label = getattr(category, "category_name", "") if category else ""
            label = label.lower()
            # The camera frame is mirrored before tracking, so MediaPipe's
            # handedness label must be swapped back to match the real hand.
            if label == "left":
                label = "right"
            elif label == "right":
                label = "left"
            handedness.append(label)
        poses = [
            make_pose(hand_landmarks, handedness[index] if index < len(handedness) else None)
            for index, hand_landmarks in enumerate(result.hand_landmarks)
        ]
        return result, poses

    def draw_landmarks(self, frame, result) -> None:
        import cv2

        height, width = frame.shape[:2]
        for hand_landmarks in result.hand_landmarks:
            pixels = [
                (
                    max(0, min(width - 1, int(landmark.x * width))),
                    max(0, min(height - 1, int(landmark.y * height))),
                )
                for landmark in hand_landmarks
            ]
            for connection in self._connections:
                cv2.line(frame, pixels[connection.start], pixels[connection.end], (0, 180, 0), 2)
            for point in pixels:
                cv2.circle(frame, point, 3, (0, 220, 220), -1)

    def close(self) -> None:
        self._landmarker.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()
