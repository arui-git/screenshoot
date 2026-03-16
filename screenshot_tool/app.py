import sys

from PyQt6.QtWidgets import QApplication

from screenshot_tool.ui.main_window import MainWindow


def run() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("Desktop Screenshot Tool")
    app.setOrganizationName("CursorDemo")

    window = MainWindow()
    window.show()

    sys.exit(app.exec())

