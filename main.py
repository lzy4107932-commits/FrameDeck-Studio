from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")
os.environ.setdefault("QT_AUTO_SCREEN_SCALE_FACTOR", "1")

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QMessageBox

from core.app_paths import APP_NAME, APP_VERSION, resource_path
from core.diagnostics import install_exception_hook
from core.startup_check import run_startup_checks
from gui.main_window import MainWindow


def show_fatal_error(message: str, log_path: str) -> None:
    QMessageBox.critical(
        None,
        "FrameDeck Studio 发生错误",
        f"软件发生未处理异常：\n\n{message}\n\n"
        f"错误日志已保存到：\n{log_path}",
    )


def main() -> None:
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationDisplayName(f"{APP_NAME} V{APP_VERSION}")
    app.setOrganizationName("FrameDeck")
    app.setWindowIcon(QIcon(resource_path("resources/icon.ico")))

    install_exception_hook(show_fatal_error)

    warnings = run_startup_checks()
    window = MainWindow(app)
    window.show()

    if warnings:
        QMessageBox.warning(
            window,
            "启动自检",
            "软件可以继续运行，但检测到以下问题：\n\n"
            + "\n".join(f"• {item}" for item in warnings),
        )

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
