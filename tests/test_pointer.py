import numpy as np
import pytest

from hand_mouse.pointer import POINTER_FINE, CursorMapper


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
