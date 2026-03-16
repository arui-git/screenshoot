from __future__ import annotations

from pathlib import Path

from PyQt6.QtWidgets import (
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)


class SettingsDialog(QDialog):
    def __init__(self, save_dir: Path, interval_ms: int, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("设置")
        self.setModal(True)

        self.save_dir_edit = QLineEdit(str(save_dir))
        browse_btn = QPushButton("选择目录")
        browse_btn.clicked.connect(self._choose_dir)

        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.addWidget(self.save_dir_edit)
        row_layout.addWidget(browse_btn)

        self.interval_box = QSpinBox()
        self.interval_box.setRange(100, 5000)
        self.interval_box.setSingleStep(50)
        self.interval_box.setValue(max(100, interval_ms))
        self.interval_box.setSuffix(" ms")

        form = QFormLayout()
        form.addRow("截图保存目录", row)
        form.addRow("连续截图间隔", self.interval_box)

        ok_btn = QPushButton("确定")
        cancel_btn = QPushButton("取消")
        ok_btn.clicked.connect(self.accept)
        cancel_btn.clicked.connect(self.reject)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        buttons.addWidget(ok_btn)
        buttons.addWidget(cancel_btn)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addLayout(buttons)

    def _choose_dir(self) -> None:
        selected = QFileDialog.getExistingDirectory(self, "选择截图保存目录", self.save_dir_edit.text())
        if selected:
            self.save_dir_edit.setText(selected)

    @property
    def save_dir(self) -> Path:
        return Path(self.save_dir_edit.text()).expanduser()

    @property
    def interval_ms(self) -> int:
        return int(self.interval_box.value())

