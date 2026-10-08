import numpy as np
import pytest

from hand_mouse.controller import DisplayBounds
from hand_mouse.detectors import HandPose


@pytest.fixture
def overlay(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from hand_mouse.overlay import SkeletonOverlay

    instance = SkeletonOverlay()
    yield instance
    instance.close()


def hand(points, handedness="right", pinch=False):
    return HandPose(np.array(points, dtype=np.float32), np.zeros(2), 0.2, pinch=pinch, handedness=handedness)


def test_skeleton_fills_screen_coordinates_and_has_only_connection_lines() -> None:
    from hand_mouse.overlay import HAND_CONNECTIONS, skeleton_lines

    points = np.zeros((21, 3))
    points[0, :2] = (0, 0)
    points[1, :2] = (1, 1)
    lines = skeleton_lines([hand(points)], 1920, 1080)
    assert len(lines) == len(HAND_CONNECTIONS) == 21
    assert lines[0] == ((0.0, 0.0), (1919.0, 1079.0))


def test_pinched_skeleton_midpoint_matches_cursor_with_display_scaling() -> None:
    from hand_mouse.overlay import skeleton_lines

    points = np.zeros((21, 3))
    points[4, :2] = (0.4, 0.4)
    points[8, :2] = (0.6, 0.4)
    points[3, :2] = (0.3, 0.5)
    display = DisplayBounds(-1920, 100, 1920, 1080)
    lines = skeleton_lines([hand(points, pinch=True)], 960, 540, (-960, 640), display)
    thumb = np.array(lines[3][1])
    index = np.array(lines[7][1])
    expected = np.array((960 * 959 / 1919, 540 * 539 / 1079))
    assert np.allclose((thumb + index) / 2, expected, atol=1e-4)
    assert np.allclose(index - thumb, (0.2 * 959, 0), atol=1e-4)


def test_left_hand_is_not_shifted_to_cursor() -> None:
    from hand_mouse.overlay import skeleton_lines

    points = np.full((21, 3), 0.5)
    lines = skeleton_lines([hand(points, "left", pinch=True)], 1001, 1001, (100, 100), DisplayBounds(0, 0, 1001, 1001))
    assert lines[0] == ((500.0, 500.0), (500.0, 500.0))


def test_live_overlay_aligns_to_actual_qt_cursor_even_if_backend_units_differ(overlay, monkeypatch) -> None:
    from PySide6.QtCore import QPoint
    from PySide6.QtGui import QCursor

    monkeypatch.setattr(QCursor, "pos", staticmethod(lambda: QPoint(400, 300)))
    overlay.live = True
    points = np.full((21, 3), 0.5)
    overlay.update([hand(points, pinch=True)], (9999, 9999), DisplayBounds(-2000, 1000, 4000, 2000))
    thumb = np.array(overlay.window.lines[3][1])
    index = np.array(overlay.window.lines[7][1])
    assert np.allclose((thumb + index) / 2, (400 - overlay.window.x(), 300 - overlay.window.y()))


def test_overlay_is_transparent_click_through_and_does_not_accept_focus(overlay) -> None:
    from PySide6.QtCore import Qt

    flags = overlay.window.windowFlags()
    assert flags & Qt.WindowType.FramelessWindowHint
    assert flags & Qt.WindowType.WindowStaysOnTopHint
    assert flags & Qt.WindowType.WindowTransparentForInput
    assert flags & Qt.WindowType.WindowDoesNotAcceptFocus
    assert overlay.window.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)


def test_overlay_has_no_camera_background_and_clears_when_hands_disappear(overlay) -> None:
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QImage

    points = np.full((21, 3), 0.25)
    points[1, :2] = (0.75, 0.25)
    overlay.update([hand(points)])
    image = QImage(overlay.window.size(), QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    overlay.window.render(image)
    assert image.pixelColor(image.width() // 2, round((image.height() - 1) * 0.25)).alpha() > 0
    assert image.pixelColor(image.width() // 2, image.height() // 2).alpha() == 0
    overlay.update([])
    image.fill(Qt.GlobalColor.transparent)
    overlay.window.render(image)
    assert image.pixelColor(image.width() // 2, round((image.height() - 1) * 0.25)).alpha() == 0


def test_bone_stroke_uses_half_opacity(overlay) -> None:
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QImage

    overlay.window.lines = [((20.0, 20.0), (200.0, 20.0))]
    image = QImage(overlay.window.size(), QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    overlay.window.render(image)
    assert 126 <= image.pixelColor(100, 20).alpha() <= 129
    assert image.pixelColor(100, 100).alpha() == 0
