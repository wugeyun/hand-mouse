import numpy as np
import pytest

from hand_mouse.pointer import POINTER_FINE, CursorMapper, PinchPointTracker


@pytest.mark.parametrize("point, expected", [((0.0, 0.0), (0, 0)), ((1.0, 1.0), (1919, 1079))])
def test_default_mapper_converges_to_a_held_camera_edge(point, expected) -> None:
    mapper = CursorMapper((1920, 1080))
    mapper.set_mode(POINTER_FINE, np.array((0.5, 0.5)), (960, 540), 0.0)
    for frame in range(1, 301):
        position = mapper.update(np.array(point), frame / 30)
    assert position == expected


def test_deadzone_accumulates_slow_movement() -> None:
    mapper = CursorMapper((1920, 1080))
    mapper.set_mode(POINTER_FINE, np.array((0.5, 0.5)), (960, 540), 0.0)
    for frame in range(1, 301):
        position = mapper.update(np.array((0.5 + frame * 0.001, 0.5)), frame / 30)
    assert position is not None
    assert abs(position[0] - round(0.8 * 1919)) < 10


def test_deadzone_rejects_jitter_around_the_accepted_point() -> None:
    mapper = CursorMapper((1001, 1001))
    mapper.set_mode(POINTER_FINE, np.array((0.5, 0.5)), (500, 500), 0.0)
    for frame in range(1, 101):
        jitter = 0.0005 if frame % 2 else -0.0005
        assert mapper.update(np.array((0.5 + jitter, 0.5)), frame / 30) == (500, 500)


def test_local_trackers_are_created_only_when_landmarks_are_lost(monkeypatch) -> None:
    calls = []

    class FakeTracker:
        def init(self, frame, box):
            self.box = box
            calls.append(("init", int(frame[0, 0, 0])))
            return True

        def update(self, frame):
            calls.append(("update", int(frame[0, 0, 0])))
            return True, self.box

    monkeypatch.setattr(PinchPointTracker, "_create_tracker", staticmethod(FakeTracker))
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    points = np.zeros((21, 3), dtype=np.float32)
    points[4, :2] = (0.4, 0.5)
    points[8, :2] = (0.45, 0.5)
    tracker = PinchPointTracker()
    tracker.remember(frame, points, 0.2)
    frame.fill(7)
    tracker.remember(frame, points, 0.2)
    assert tracker.active
    assert calls == []
    # Preview drawing must not change the saved reference image.
    frame.fill(9)
    midpoint = tracker.update(frame)
    assert calls == [("init", 7), ("init", 7), ("update", 9), ("update", 9)]
    assert np.allclose(midpoint, (0.425, 0.5))
    tracker.reset()
    assert not tracker.active
    assert tracker.update(frame) is None


def test_failed_fallback_initialization_stops_tracking(monkeypatch) -> None:
    monkeypatch.setattr(PinchPointTracker, "_create_tracker", staticmethod(lambda: None))
    tracker = PinchPointTracker()
    tracker.remember(np.zeros((100, 100, 3), dtype=np.uint8), np.zeros((21, 3)), 0.2)
    assert tracker.update(np.zeros((100, 100, 3), dtype=np.uint8)) is None
    assert not tracker.active
