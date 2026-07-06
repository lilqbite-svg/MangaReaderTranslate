"""Phase 2 desktop entry point.

    python -m app.main
"""
from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from app.ui.main_window import MainWindow
from app.ui.theme import STYLESHEET


def _icon_path() -> Path:
    # PyInstaller bundles pure-Python modules into a compressed archive rather
    # than extracting them, so a frozen module's __file__ is a synthetic path
    # that doesn't necessarily match where data files (like this icon) were
    # actually extracted to. sys._MEIPASS is the officially documented,
    # reliable base for locating bundled data at runtime when frozen (same
    # approach already used in gpu_bootstrap.py for the nvidia DLLs).
    if getattr(sys, "frozen", False):
        base = Path(sys._MEIPASS)
    else:
        base = Path(__file__).resolve().parent.parent
    return base / "resources" / "icon" / "app.ico"


ICON_PATH = _icon_path()


def main() -> None:
    app = QApplication(sys.argv)
    app.setStyleSheet(STYLESHEET)
    if ICON_PATH.exists():
        app.setWindowIcon(QIcon(str(ICON_PATH)))
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
