from __future__ import annotations

import time
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import QRect, QSettings, QSize, Qt, QTimer, QUrl
from PyQt6.QtGui import QDesktopServices, QIcon, QKeySequence, QPixmap, QShortcut
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
    QDialog,
)

from screenshot_tool.core.history_manager import HistoryManager
from screenshot_tool.core.image_saver import ImageSaver
from screenshot_tool.core.screen_capture import ScreenCapture
from screenshot_tool.services.hotkey_manager import HotkeyManager
from screenshot_tool.ui.region_selector import RegionSelectorOverlay
from screenshot_tool.ui.settings_dialog import SettingsDialog


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("桌面截图工具")
        self.resize(980, 660)

        self.settings = QSettings("CursorDemo", "DesktopScreenshotTool")
        default_save_dir = Path.home() / "Pictures" / "DesktopScreenshots"
        save_dir = Path(self.settings.value("save_dir", str(default_save_dir)))
        self.capture_interval_ms = max(100, int(self.settings.value("interval_ms", 500)))

        self.capture_engine = ScreenCapture()
        self.image_saver = ImageSaver(save_dir)
        self.history_manager = HistoryManager(save_dir, max_items=10)
        self.hotkeys = HotkeyManager()
        self.selector = RegionSelectorOverlay(self.capture_engine)

        self.current_region: Optional[QRect] = None
        self._continuous_running = False
        self._continuous_by_hotkey = False

        self.continuous_timer = QTimer(self)
        self.continuous_timer.setInterval(self.capture_interval_ms)
        self.continuous_timer.timeout.connect(self._continuous_tick)

        self._build_ui()
        self._bind_shortcuts()
        self._bind_events()
        self._refresh_history()

        self.hotkeys.start()

    def _build_ui(self) -> None:
        container = QWidget(self)
        self.setCentralWidget(container)
        root = QVBoxLayout(container)

        self.btn_start = QPushButton("开始截图")
        self.btn_reselect = QPushButton("重新选择")
        self.btn_capture = QPushButton("截图")
        self.btn_continuous = QPushButton("连续截图")
        self.btn_open_dir = QPushButton("打开截图目录")
        self.btn_settings = QPushButton("设置")

        top = QHBoxLayout()
        top.addWidget(self.btn_start)
        top.addWidget(self.btn_reselect)
        top.addWidget(self.btn_capture)
        top.addWidget(self.btn_continuous)
        top.addWidget(self.btn_open_dir)
        top.addStretch(1)
        top.addWidget(self.btn_settings)
        root.addLayout(top)

        self.region_label = QLabel("当前区域：未选择")
        self.status_label = QLabel("提示：点击“开始截图”或按 Ctrl+Shift+S 进入截图模式")
        root.addWidget(self.region_label)
        root.addWidget(self.status_label)

        self.history_title = QLabel("最近截图（最多10张）")
        root.addWidget(self.history_title)

        self.history_list = QListWidget()
        self.history_list.setViewMode(QListWidget.ViewMode.IconMode)
        self.history_list.setIconSize(QSize(180, 100))
        self.history_list.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.history_list.setMovement(QListWidget.Movement.Static)
        self.history_list.setWordWrap(True)
        self.history_list.setSpacing(10)
        root.addWidget(self.history_list, stretch=1)

    def _bind_shortcuts(self) -> None:
        QShortcut(QKeySequence("Ctrl+Shift+S"), self, activated=self.start_selection)
        QShortcut(QKeySequence("Return"), self, activated=self.capture_once)
        QShortcut(QKeySequence("Enter"), self, activated=self.capture_once)
        QShortcut(QKeySequence("R"), self, activated=self.start_selection)

    def _bind_events(self) -> None:
        self.btn_start.clicked.connect(self.start_selection)
        self.btn_reselect.clicked.connect(self.start_selection)
        self.btn_capture.clicked.connect(self.capture_once)
        self.btn_continuous.clicked.connect(self.toggle_continuous)
        self.btn_open_dir.clicked.connect(self.open_save_dir)
        self.btn_settings.clicked.connect(self.open_settings)

        self.selector.region_changed.connect(self._on_region_changed)
        self.selector.selection_confirmed.connect(self._on_region_confirmed)
        self.selector.capture_requested.connect(self._capture_from_selector)

        self.hotkeys.start_selection.connect(self.start_selection)
        self.hotkeys.continuous_pressed.connect(self._hotkey_continuous_start)
        self.hotkeys.continuous_released.connect(self._hotkey_continuous_stop)
        self.hotkeys.error.connect(self._on_hotkey_error)

        self.history_list.itemDoubleClicked.connect(self.open_history_item)
        self.history_list.itemClicked.connect(self.open_history_item)

    def _on_region_changed(self, region) -> None:
        self.current_region = region
        self._update_region_label()

    def _on_region_confirmed(self, region) -> None:
        self.current_region = region
        self._update_region_label()

    def _capture_from_selector(self, region) -> None:
        self.current_region = region
        self.capture_once()

    def _update_region_label(self) -> None:
        if not self.current_region:
            self.region_label.setText("当前区域：未选择")
            return
        region = self.current_region
        self.region_label.setText(
            f"当前区域：x={region.x()}, y={region.y()}, 宽={region.width()}, 高={region.height()}"
        )

    def start_selection(self) -> None:
        self.selector.open_selector(self.current_region)
        self.status_label.setText("截图模式：拖动选择区域，Enter 截图，R 重选，Esc 退出")

    def capture_once(self, silent: bool = False) -> bool:
        if self.current_region is None or self.current_region.width() <= 1 or self.current_region.height() <= 1:
            if not silent:
                QMessageBox.information(self, "提示", "请先选择截图区域。")
            return False

        begin = time.perf_counter()
        pixmap = self.capture_engine.capture_region(self.current_region)
        if pixmap.isNull():
            if not silent:
                QMessageBox.warning(self, "失败", "截图失败，请重新选择区域后重试。")
            return False

        try:
            saved_path = self.image_saver.save_pixmap(pixmap)
        except Exception as exc:  # pragma: no cover - IO exceptions
            if not silent:
                QMessageBox.critical(self, "保存失败", str(exc))
            return False

        elapsed_ms = (time.perf_counter() - begin) * 1000
        self._refresh_history()
        self.status_label.setText(f"已保存：{saved_path.name} | 截图耗时：{elapsed_ms:.1f} ms")
        return True

    def toggle_continuous(self) -> None:
        if self._continuous_running:
            self.stop_continuous()
        else:
            self.start_continuous(by_hotkey=False)

    def start_continuous(self, by_hotkey: bool) -> None:
        if self._continuous_running:
            return
        if self.current_region is None:
            self.status_label.setText("连续截图前请先选择区域。")
            if not by_hotkey:
                QMessageBox.information(self, "提示", "连续截图前请先选择区域。")
            return

        self._continuous_by_hotkey = by_hotkey
        self._continuous_running = True
        self.continuous_timer.start(max(100, self.capture_interval_ms))
        self.btn_continuous.setText("停止连续截图")
        self.status_label.setText(
            f"连续截图中：间隔 {max(100, self.capture_interval_ms)}ms，松开 F8 或点击按钮停止。"
        )
        self.capture_once(silent=True)

    def stop_continuous(self) -> None:
        if not self._continuous_running:
            return
        self.continuous_timer.stop()
        self._continuous_running = False
        self._continuous_by_hotkey = False
        self.btn_continuous.setText("连续截图")
        self.status_label.setText("连续截图已停止。")

    def _continuous_tick(self) -> None:
        ok = self.capture_once(silent=True)
        if not ok:
            self.stop_continuous()

    def _hotkey_continuous_start(self) -> None:
        self.start_continuous(by_hotkey=True)

    def _hotkey_continuous_stop(self) -> None:
        if self._continuous_running and self._continuous_by_hotkey:
            self.stop_continuous()

    def _on_hotkey_error(self, message: str) -> None:
        self.status_label.setText(message)

    def _refresh_history(self) -> None:
        self.history_list.clear()
        for image_path in self.history_manager.list_recent():
            pixmap = QPixmap(str(image_path))
            if pixmap.isNull():
                continue
            thumb = pixmap.scaled(
                self.history_list.iconSize(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            item = QListWidgetItem(QIcon(thumb), image_path.name)
            item.setData(Qt.ItemDataRole.UserRole, str(image_path))
            item.setToolTip(str(image_path))
            self.history_list.addItem(item)

    def open_history_item(self, item: QListWidgetItem) -> None:
        path = item.data(Qt.ItemDataRole.UserRole)
        if not path:
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    def open_save_dir(self) -> None:
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.image_saver.save_dir)))

    def open_settings(self) -> None:
        dialog = SettingsDialog(
            save_dir=self.image_saver.save_dir,
            interval_ms=self.capture_interval_ms,
            parent=self,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        self.capture_interval_ms = max(100, dialog.interval_ms)
        self.continuous_timer.setInterval(self.capture_interval_ms)
        self.image_saver.set_save_dir(dialog.save_dir)
        self.history_manager.set_save_dir(dialog.save_dir)
        self.settings.setValue("save_dir", str(dialog.save_dir))
        self.settings.setValue("interval_ms", int(self.capture_interval_ms))
        self._refresh_history()
        self.status_label.setText("设置已保存。")

    def closeEvent(self, event) -> None:
        self.continuous_timer.stop()
        self.hotkeys.stop()
        self.selector.hide()
        super().closeEvent(event)

