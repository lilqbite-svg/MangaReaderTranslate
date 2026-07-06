from __future__ import annotations

# Flat dark theme applied app-wide via QApplication.setStyleSheet(). Kept as
# one file so colors stay consistent across every widget without threading
# a dozen inline styleSheet= calls through the UI code.

BG = "#1c1d27"
PANEL = "#242531"
PANEL_ALT = "#2b2c3a"
BORDER = "#3a3c4f"
TEXT = "#e4e4ec"
TEXT_DIM = "#9a9bb0"
ACCENT = "#6c8cff"
ACCENT_HOVER = "#8aa3ff"
ACCENT_PRESSED = "#5776e0"
DANGER = "#e06c75"

STYLESHEET = f"""
QMainWindow, QDialog {{
    background: {BG};
}}

QWidget {{
    background: transparent;
    color: {TEXT};
    font-family: "Segoe UI", sans-serif;
    font-size: 13px;
}}

QLabel {{
    background: transparent;
}}

QLabel[role="heading"] {{
    color: {TEXT_DIM};
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.5px;
    text-transform: uppercase;
    padding: 2px 0;
}}

QLabel[role="status"] {{
    color: {TEXT_DIM};
    padding: 4px 10px;
}}

#TopBar {{
    background: {PANEL};
    border-bottom: 1px solid {BORDER};
}}

#SidePanel {{
    background: {PANEL};
    border-right: 1px solid {BORDER};
}}

QMenuBar {{
    background: {PANEL};
    color: {TEXT};
    border-bottom: 1px solid {BORDER};
    padding: 2px;
}}
QMenuBar::item {{
    padding: 6px 12px;
    border-radius: 4px;
}}
QMenuBar::item:selected {{
    background: {PANEL_ALT};
}}
QMenu {{
    background: {PANEL};
    color: {TEXT};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 4px;
}}
QMenu::item {{
    padding: 6px 24px 6px 12px;
    border-radius: 4px;
}}
QMenu::item:selected {{
    background: {ACCENT};
    color: white;
}}
QMenu::separator {{
    height: 1px;
    background: {BORDER};
    margin: 4px 6px;
}}

QComboBox, QLineEdit, QPlainTextEdit, QTextEdit {{
    background: {PANEL_ALT};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 5px 8px;
    color: {TEXT};
    selection-background-color: {ACCENT};
}}
QComboBox:hover, QLineEdit:hover, QPlainTextEdit:hover {{
    border-color: {ACCENT};
}}
QComboBox:focus, QLineEdit:focus, QPlainTextEdit:focus {{
    border-color: {ACCENT};
}}
QComboBox::drop-down {{
    border: none;
    width: 22px;
}}
QComboBox QAbstractItemView {{
    background: {PANEL_ALT};
    border: 1px solid {BORDER};
    border-radius: 6px;
    selection-background-color: {ACCENT};
    outline: none;
    padding: 4px;
}}

QPushButton {{
    background: {PANEL_ALT};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 7px 16px;
    color: {TEXT};
}}
QPushButton:hover {{
    border-color: {ACCENT};
    color: white;
}}
QPushButton:pressed {{
    background: {ACCENT_PRESSED};
}}
QPushButton:disabled {{
    color: {TEXT_DIM};
    border-color: {BORDER};
}}

QPushButton[role="primary"] {{
    background: {ACCENT};
    border: 1px solid {ACCENT};
    color: white;
    font-weight: 600;
}}
QPushButton[role="primary"]:hover {{
    background: {ACCENT_HOVER};
    border-color: {ACCENT_HOVER};
}}
QPushButton[role="primary"]:pressed {{
    background: {ACCENT_PRESSED};
}}
QPushButton[role="primary"]:disabled {{
    background: {PANEL_ALT};
    border-color: {BORDER};
    color: {TEXT_DIM};
}}

QPushButton[role="danger"]:hover {{
    border-color: {DANGER};
    color: {DANGER};
}}

QListWidget {{
    background: {PANEL_ALT};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 4px;
    outline: none;
}}
QListWidget::item {{
    padding: 7px 8px;
    border-radius: 5px;
    margin: 1px 0;
}}
QListWidget::item:selected {{
    background: {ACCENT};
    color: white;
}}
QListWidget::item:hover:!selected {{
    background: {PANEL};
}}

QProgressBar {{
    background: {PANEL_ALT};
    border: 1px solid {BORDER};
    border-radius: 6px;
    height: 8px;
    text-align: center;
    color: transparent;
}}
QProgressBar::chunk {{
    background: {ACCENT};
    border-radius: 5px;
}}

QScrollArea {{
    border: none;
    background: transparent;
}}
QScrollArea > QWidget > QWidget {{
    background: transparent;
}}

QScrollBar:vertical {{
    background: transparent;
    width: 12px;
    margin: 2px;
}}
QScrollBar::handle:vertical {{
    background: {BORDER};
    border-radius: 5px;
    min-height: 24px;
}}
QScrollBar::handle:vertical:hover {{
    background: {ACCENT};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}
QScrollBar:horizontal {{
    background: transparent;
    height: 12px;
    margin: 2px;
}}
QScrollBar::handle:horizontal {{
    background: {BORDER};
    border-radius: 5px;
    min-width: 24px;
}}
QScrollBar::handle:horizontal:hover {{
    background: {ACCENT};
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0;
}}

QCheckBox {{
    spacing: 8px;
}}
QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border: 1px solid {BORDER};
    border-radius: 4px;
    background: {PANEL_ALT};
}}
QCheckBox::indicator:checked {{
    background: {ACCENT};
    border-color: {ACCENT};
}}

QSplitter::handle {{
    background: {BORDER};
    width: 2px;
}}
QSplitter::handle:hover {{
    background: {ACCENT};
}}

QStatusBar {{
    background: {PANEL};
    border-top: 1px solid {BORDER};
    color: {TEXT_DIM};
}}

QToolTip {{
    background: {PANEL_ALT};
    color: {TEXT};
    border: 1px solid {BORDER};
    border-radius: 4px;
    padding: 4px 6px;
}}

QDialogButtonBox QPushButton {{
    min-width: 72px;
}}
"""
