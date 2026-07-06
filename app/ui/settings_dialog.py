from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from app.config import get_settings

_DEVICE_OPTIONS = [("Auto (try GPU, fall back to CPU)", "auto"), ("CPU only", "cpu"), ("GPU only", "cuda")]
_READING_MODE_OPTIONS = [("Horizontal (Left/Right)", "horizontal"), ("Vertical (Up/Down)", "vertical")]
_FONT_FILTER = "Fonts (*.ttf *.otf *.ttc)"


def _heading(text: str) -> QLabel:
    label = QLabel(text)
    label.setProperty("role", "heading")
    return label


class SettingsDialog(QDialog):
    """OCR-backend override (manga-ocr is the default for Japanese, RapidOCR
    handles everything else), device preference (auto/CPU/GPU) for inference,
    and an app-wide custom font (used wherever a page or box doesn't have its
    own font override)."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumWidth(360)

        self._settings = get_settings()
        self._font_path = self._settings.value("global_font_path", "")

        self.force_rapidocr_ja = QCheckBox("Use RapidOCR for Japanese (instead of manga-ocr)")
        self.force_rapidocr_ja.setChecked(self._settings.value("force_rapidocr_ja", False, type=bool))

        self.device_combo = QComboBox()
        for label, value in _DEVICE_OPTIONS:
            self.device_combo.addItem(label, value)
        current_device = self._settings.value("device", "auto")
        index = self.device_combo.findData(current_device)
        self.device_combo.setCurrentIndex(index if index >= 0 else 0)

        self.reading_mode_combo = QComboBox()
        for label, value in _READING_MODE_OPTIONS:
            self.reading_mode_combo.addItem(label, value)
        current_mode = self._settings.value("reading_mode", "horizontal")
        mode_index = self.reading_mode_combo.findData(current_mode)
        self.reading_mode_combo.setCurrentIndex(mode_index if mode_index >= 0 else 0)

        self.font_label = QLabel()
        self.font_label.setWordWrap(True)
        self._refresh_font_label()
        font_choose = QPushButton("Choose...")
        font_choose.clicked.connect(self._choose_font)
        font_clear = QPushButton("Use Default")
        font_clear.clicked.connect(self._clear_font)
        font_row = QHBoxLayout()
        font_row.setSpacing(8)
        font_row.addWidget(font_choose)
        font_row.addWidget(font_clear)
        font_row.addStretch()

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._save_and_accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 16)
        layout.setSpacing(8)
        layout.addWidget(_heading("OCR Backend"))
        layout.addWidget(self.force_rapidocr_ja)
        layout.addSpacing(12)
        layout.addWidget(_heading("Device"))
        layout.addWidget(self.device_combo)
        layout.addSpacing(12)
        layout.addWidget(_heading("Reading Mode (where the hover page-turn buttons sit; arrow keys always work)"))
        layout.addWidget(self.reading_mode_combo)
        layout.addSpacing(12)
        layout.addWidget(_heading("Custom Font (applies everywhere, unless a page or box overrides it)"))
        layout.addWidget(self.font_label)
        layout.addLayout(font_row)
        layout.addSpacing(16)
        layout.addWidget(buttons)

    def _refresh_font_label(self) -> None:
        self.font_label.setText(f"Current: {Path(self._font_path).name}" if self._font_path else "Current: Default")

    def _choose_font(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Choose Font", "", _FONT_FILTER)
        if path:
            self._font_path = path
            self._refresh_font_label()

    def _clear_font(self) -> None:
        self._font_path = ""
        self._refresh_font_label()

    def _save_and_accept(self) -> None:
        self._settings.setValue("force_rapidocr_ja", self.force_rapidocr_ja.isChecked())
        self._settings.setValue("device", self.device_combo.currentData())
        self._settings.setValue("reading_mode", self.reading_mode_combo.currentData())
        self._settings.setValue("global_font_path", self._font_path)
        self.accept()


def get_ocr_backend_overrides() -> dict[str, str]:
    settings = get_settings()
    overrides: dict[str, str] = {}
    if settings.value("force_rapidocr_ja", False, type=bool):
        overrides["ja"] = "rapidocr"
    return overrides


def get_device_preference() -> str:
    return get_settings().value("device", "auto")


def get_global_font_path() -> str:
    return get_settings().value("global_font_path", "")


def get_reading_mode() -> str:
    return get_settings().value("reading_mode", "horizontal")
