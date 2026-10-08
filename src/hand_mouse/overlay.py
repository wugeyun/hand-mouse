"""Transparent desktop skeleton lines with no camera image or status UI."""

from __future__ import annotations

import sys

import numpy as np
from PySide6.QtCore import QLineF, Qt
from PySide6.QtGui import QColor, QCursor, QPainter, QPen
from PySide6.QtWidgets import QApplication, QWidget

from .controller import DisplayBounds
from .detectors import HandPose, pinch_point

HAND_CONNECTIONS = (
    (0, 1), (1, 2), (2, 3), (3, 4),
    (0, 5), (5, 6), (6, 7), (7, 8),
    (5, 9), (9, 10), (10, 11), (11, 12),
    (9, 13), (13, 14), (14, 15), (15, 16),
    (13, 17), (0, 17), (17, 18), (18, 19), (19, 20),
)

Point = tuple[float, float]
Line = tuple[Point, Point]


def skeleton_lines(
    hands: list[HandPose],
    width: int,
    height: int,
    cursor_position: tuple[int, int] | None = None,
    display: DisplayBounds | None = None,
) -> list[Line]:
    """Scale to the full screen and align a right pinch with the actual cursor."""
    scale = np.array((width - 1, height - 1), dtype=np.float64)
    lines = []
    for hand in hands:
        points = np.clip(hand.points[:, :2].astype(np.float64), 0.0, 1.0) * scale
        if hand.handedness == "right" and hand.pinch and cursor_position is not None and display is not None:
            cursor = np.array((cursor_position[0] - display.x, cursor_position[1] - display.y), dtype=np.float64)
            cursor *= scale / np.array((max(display.width - 1, 1), max(display.height - 1, 1)))
            points += cursor - np.clip(pinch_point(hand.points), 0.0, 1.0) * scale
        lines.extend((tuple(points[start]), tuple(points[end])) for start, end in HAND_CONNECTIONS)
    return lines


class _SkeletonWindow(QWidget):
    def __init__(self) -> None:
        super().__init__(None, (
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.WindowTransparentForInput
            | Qt.WindowType.WindowDoesNotAcceptFocus
            | Qt.WindowType.NoDropShadowWindowHint
        ))
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_MacAlwaysShowToolWindow)
        self.lines: list[Line] = []

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
        painter.fillRect(self.rect(), Qt.GlobalColor.transparent)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setOpacity(0.5)
        painter.setPen(QPen(QColor("#00e676"), 3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        for start, end in self.lines:
            painter.drawLine(QLineF(*start, *end))
        painter.end()


class SkeletonOverlay:
    """A screen-sized, click-through window that never accepts keyboard focus."""

    def __init__(self, live: bool = False) -> None:
        self.live = live
        self.application = QApplication.instance()
        if self.application is None:
            if sys.platform == "darwin":
                # A background overlay must not activate Qt's macOS application.
                QApplication.setAttribute(Qt.ApplicationAttribute.AA_PluginApplication)
            self.application = QApplication([])
            if self.application.platformName() == "cocoa":
                self._prepare_macos_application()
        self.application.setQuitOnLastWindowClosed(False)
        self.window = _SkeletonWindow()
        self._place_on_cursor_screen()
        if self.application.platformName() == "cocoa":
            self._join_macos_spaces()
        self.window.show()
        self.application.processEvents()

    def _prepare_macos_application(self) -> None:
        from AppKit import (
            NSApplication,
            NSApplicationActivationPolicyAccessory,
            NSApplicationActivationPolicyProhibited,
        )

        application = NSApplication.sharedApplication()
        # Complete Qt's startup activation before any overlay window is shown.
        application.setActivationPolicy_(NSApplicationActivationPolicyProhibited)
        self.application.processEvents()
        application.setActivationPolicy_(NSApplicationActivationPolicyAccessory)

    def _join_macos_spaces(self) -> None:
        import ctypes

        import objc
        from AppKit import NSWindowCollectionBehaviorCanJoinAllSpaces, NSWindowCollectionBehaviorFullScreenAuxiliary

        view = objc.objc_object(c_void_p=ctypes.c_void_p(int(self.window.winId())))
        view.window().setCollectionBehavior_(
            NSWindowCollectionBehaviorCanJoinAllSpaces | NSWindowCollectionBehaviorFullScreenAuxiliary,
        )

    def _place_on_cursor_screen(self) -> None:
        screen = self.application.screenAt(QCursor.pos()) or self.application.primaryScreen()
        if screen is None:
            raise RuntimeError("no desktop screen is available for the skeleton overlay")
        if self.window.geometry() != screen.geometry():
            self.window.setGeometry(screen.geometry())

    def update(
        self,
        hands: list[HandPose],
        cursor_position: tuple[int, int] | None = None,
        display: DisplayBounds | None = None,
    ) -> None:
        self._place_on_cursor_screen()
        if self.live:
            # Qt cursor and window coordinates share the same DPI/origin units.
            cursor = QCursor.pos()
            geometry = self.window.geometry()
            cursor_position = cursor.x(), cursor.y()
            display = DisplayBounds(geometry.x(), geometry.y(), geometry.width(), geometry.height())
        self.window.lines = skeleton_lines(hands, self.window.width(), self.window.height(), cursor_position, display)
        self.window.update()
        self.application.processEvents()

    def close(self) -> None:
        self.window.close()
        self.application.processEvents()
