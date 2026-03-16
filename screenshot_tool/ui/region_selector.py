from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from PyQt6.QtCore import QPoint, QRect, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QCursor, QMouseEvent, QPainter, QPaintEvent, QPen
from PyQt6.QtWidgets import QWidget

from screenshot_tool.core.screen_capture import ScreenCapture


@dataclass(frozen=True)
class ResizeHit:
    name: str
    cursor: Qt.CursorShape


class RegionSelectorOverlay(QWidget):
    region_changed = pyqtSignal(QRect)
    selection_confirmed = pyqtSignal(QRect)
    capture_requested = pyqtSignal(QRect)
    cancelled = pyqtSignal()

    HANDLE_SIZE = 8
    MIN_SIZE = 20

    _HITS = (
        ResizeHit("nw", Qt.CursorShape.SizeFDiagCursor),
        ResizeHit("n", Qt.CursorShape.SizeVerCursor),
        ResizeHit("ne", Qt.CursorShape.SizeBDiagCursor),
        ResizeHit("w", Qt.CursorShape.SizeHorCursor),
        ResizeHit("e", Qt.CursorShape.SizeHorCursor),
        ResizeHit("sw", Qt.CursorShape.SizeBDiagCursor),
        ResizeHit("s", Qt.CursorShape.SizeVerCursor),
        ResizeHit("se", Qt.CursorShape.SizeFDiagCursor),
    )

    def __init__(self, capture: ScreenCapture) -> None:
        super().__init__()
        self._capture = capture
        self._background = None
        self._selection: Optional[QRect] = None
        self._drag_mode = "none"
        self._resize_hit: Optional[ResizeHit] = None
        self._drag_start = QPoint()
        self._move_offset = QPoint()
        self._resize_origin = QRect()

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    @property
    def selection_global(self) -> Optional[QRect]:
        if not self._selection:
            return None
        return self._to_global_rect(self._selection)

    def open_selector(self, initial_region: Optional[QRect] = None) -> None:
        self._capture.refresh()
        virtual = self._capture.virtual_geometry
        self.setGeometry(virtual)
        self._background = self._capture.grab_virtual_desktop()

        self._selection = None
        if initial_region and initial_region.isValid():
            local = initial_region.translated(-virtual.x(), -virtual.y())
            local = local.intersected(self.rect())
            if local.width() > 1 and local.height() > 1:
                self._selection = local
                self._emit_region_changed()

        self._drag_mode = "none"
        self._resize_hit = None
        self.show()
        self.raise_()
        self.activateWindow()
        self.setFocus()
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        if self._background and not self._background.isNull():
            painter.drawPixmap(0, 0, self._background)
        else:
            painter.fillRect(self.rect(), QColor(0, 0, 0))

        painter.fillRect(self.rect(), QColor(0, 0, 0, 130))

        if self._selection and self._selection.isValid():
            if self._background and not self._background.isNull():
                painter.drawPixmap(self._selection, self._background, self._selection)
            painter.setPen(QPen(QColor(0, 170, 255), 2))
            painter.drawRect(self._selection)
            self._draw_handles(painter, self._selection)
            self._draw_size_text(painter, self._selection)
        else:
            painter.setPen(QColor(255, 255, 255))
            painter.drawText(
                self.rect(),
                Qt.AlignmentFlag.AlignCenter,
                "拖动鼠标选择截图区域\nEnter 确认截图，R 重新选择，Esc 退出",
            )

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return
        pos = event.position().toPoint()
        self._drag_start = pos

        if self._selection and self._selection.contains(pos):
            hit = self._hit_test(pos)
            if hit:
                self._drag_mode = "resize"
                self._resize_hit = hit
                self._resize_origin = QRect(self._selection)
                self.setCursor(hit.cursor)
            else:
                self._drag_mode = "move"
                self._move_offset = pos - self._selection.topLeft()
                self.setCursor(Qt.CursorShape.SizeAllCursor)
            return

        hit = self._hit_test(pos)
        if hit and self._selection:
            self._drag_mode = "resize"
            self._resize_hit = hit
            self._resize_origin = QRect(self._selection)
            self.setCursor(hit.cursor)
            return

        self._drag_mode = "select"
        self._selection = QRect(pos, pos)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.update()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        pos = event.position().toPoint()
        if self._drag_mode == "select":
            self._selection = self._normalize_rect(self._drag_start, pos)
            self._emit_region_changed()
            self.update()
            return

        if self._drag_mode == "move" and self._selection:
            rect = QRect(self._selection)
            target = pos - self._move_offset
            max_x = max(0, self.width() - rect.width())
            max_y = max(0, self.height() - rect.height())
            x = min(max(target.x(), 0), max_x)
            y = min(max(target.y(), 0), max_y)
            rect.moveTo(x, y)
            self._selection = rect
            self._emit_region_changed()
            self.update()
            return

        if self._drag_mode == "resize" and self._selection and self._resize_hit:
            self._selection = self._resize_rect(self._resize_origin, pos, self._resize_hit.name)
            self._emit_region_changed()
            self.update()
            return

        self._update_hover_cursor(pos)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return
        self._drag_mode = "none"
        self._resize_hit = None
        self._update_hover_cursor(event.position().toPoint())

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self._selection_valid():
            self._confirm_and_capture()

    def keyPressEvent(self, event) -> None:
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if self._selection_valid():
                self._confirm_and_capture()
            return

        if event.key() == Qt.Key.Key_R:
            self._selection = None
            self._drag_mode = "none"
            self._resize_hit = None
            self.setCursor(Qt.CursorShape.CrossCursor)
            self.update()
            return

        if event.key() == Qt.Key.Key_Escape:
            self.hide()
            self.cancelled.emit()
            return

        super().keyPressEvent(event)

    def _confirm_and_capture(self) -> None:
        if not self._selection:
            return
        global_rect = self._to_global_rect(self._selection)
        self.selection_confirmed.emit(global_rect)
        self.capture_requested.emit(global_rect)
        self.hide()

    def _selection_valid(self) -> bool:
        return self._selection is not None and self._selection.width() > 1 and self._selection.height() > 1

    def _normalize_rect(self, a: QPoint, b: QPoint) -> QRect:
        left = min(a.x(), b.x())
        right = max(a.x(), b.x())
        top = min(a.y(), b.y())
        bottom = max(a.y(), b.y())
        left = min(max(left, 0), self.width() - 1)
        right = min(max(right, 0), self.width() - 1)
        top = min(max(top, 0), self.height() - 1)
        bottom = min(max(bottom, 0), self.height() - 1)
        return QRect(QPoint(left, top), QPoint(right, bottom))

    def _resize_rect(self, origin: QRect, pos: QPoint, handle: str) -> QRect:
        left = origin.left()
        right = origin.right()
        top = origin.top()
        bottom = origin.bottom()

        if "w" in handle:
            left = min(max(pos.x(), 0), right - self.MIN_SIZE)
        if "e" in handle:
            right = max(min(pos.x(), self.width() - 1), left + self.MIN_SIZE)
        if "n" in handle:
            top = min(max(pos.y(), 0), bottom - self.MIN_SIZE)
        if "s" in handle:
            bottom = max(min(pos.y(), self.height() - 1), top + self.MIN_SIZE)

        return QRect(QPoint(left, top), QPoint(right, bottom)).normalized()

    def _update_hover_cursor(self, pos: QPoint) -> None:
        if self._drag_mode != "none":
            return
        if self._selection and self._selection.contains(pos):
            hit = self._hit_test(pos)
            if hit:
                self.setCursor(hit.cursor)
            else:
                self.setCursor(Qt.CursorShape.SizeAllCursor)
            return
        hit = self._hit_test(pos)
        if hit:
            self.setCursor(hit.cursor)
            return
        self.setCursor(Qt.CursorShape.CrossCursor)

    def _draw_handles(self, painter: QPainter, rect: QRect) -> None:
        painter.setBrush(QColor(0, 170, 255))
        painter.setPen(Qt.PenStyle.NoPen)
        half = self.HANDLE_SIZE // 2
        for point in self._handle_points(rect):
            painter.drawRect(point.x() - half, point.y() - half, self.HANDLE_SIZE, self.HANDLE_SIZE)

    def _draw_size_text(self, painter: QPainter, rect: QRect) -> None:
        text = f"{rect.width()} × {rect.height()}"
        metrics = painter.fontMetrics()
        tw = metrics.horizontalAdvance(text) + 14
        th = metrics.height() + 8
        x = rect.left()
        y = rect.top() - th - 8
        if y < 0:
            y = rect.bottom() + 8
        if x + tw > self.width():
            x = self.width() - tw - 4
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(20, 20, 20, 200))
        painter.drawRoundedRect(x, y, tw, th, 6, 6)
        painter.setPen(QColor(255, 255, 255))
        painter.drawText(QRect(x, y, tw, th), Qt.AlignmentFlag.AlignCenter, text)

    def _handle_points(self, rect: QRect) -> list[QPoint]:
        cx = rect.center().x()
        cy = rect.center().y()
        return [
            rect.topLeft(),
            QPoint(cx, rect.top()),
            rect.topRight(),
            QPoint(rect.left(), cy),
            QPoint(rect.right(), cy),
            rect.bottomLeft(),
            QPoint(cx, rect.bottom()),
            rect.bottomRight(),
        ]

    def _hit_test(self, pos: QPoint) -> Optional[ResizeHit]:
        if not self._selection:
            return None
        points = self._handle_points(self._selection)
        for hit, point in zip(self._HITS, points):
            area = QRect(
                point.x() - self.HANDLE_SIZE,
                point.y() - self.HANDLE_SIZE,
                self.HANDLE_SIZE * 2,
                self.HANDLE_SIZE * 2,
            )
            if area.contains(pos):
                return hit
        return None

    def _emit_region_changed(self) -> None:
        if self._selection_valid():
            self.region_changed.emit(self._to_global_rect(self._selection))

    def _to_global_rect(self, rect: QRect) -> QRect:
        origin = self.geometry().topLeft()
        return rect.translated(origin.x(), origin.y())

