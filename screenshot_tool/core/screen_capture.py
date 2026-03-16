from __future__ import annotations

from PyQt6.QtCore import QRect
from PyQt6.QtGui import QGuiApplication, QPixmap


class ScreenCapture:
    """Responsible for screen grabbing and multi-monitor geometry management."""

    def __init__(self) -> None:
        self._virtual_geometry = self._compute_virtual_geometry()

    @property
    def virtual_geometry(self) -> QRect:
        return QRect(self._virtual_geometry)

    def refresh(self) -> None:
        self._virtual_geometry = self._compute_virtual_geometry()

    def _compute_virtual_geometry(self) -> QRect:
        screens = QGuiApplication.screens()
        if not screens:
            return QRect(0, 0, 1, 1)

        virtual = QRect(screens[0].geometry())
        for screen in screens[1:]:
            virtual = virtual.united(screen.geometry())
        return virtual

    def grab_virtual_desktop(self) -> QPixmap:
        self.refresh()
        primary = QGuiApplication.primaryScreen()
        if primary is None:
            return QPixmap()
        vg = self.virtual_geometry
        return primary.grabWindow(0, vg.x(), vg.y(), vg.width(), vg.height())

    def capture_region(self, region: QRect) -> QPixmap:
        """Capture a global screen region."""
        if region.width() <= 0 or region.height() <= 0:
            return QPixmap()

        self.refresh()
        primary = QGuiApplication.primaryScreen()
        if primary is None:
            return QPixmap()

        x = region.x()
        y = region.y()
        w = region.width()
        h = region.height()
        pixmap = primary.grabWindow(0, x, y, w, h)
        if not pixmap.isNull():
            return pixmap

        # Fallback path for environments where direct regional grab fails.
        desktop = self.grab_virtual_desktop()
        if desktop.isNull():
            return QPixmap()
        offset = self.virtual_geometry.topLeft()
        return desktop.copy(region.translated(-offset.x(), -offset.y()))

