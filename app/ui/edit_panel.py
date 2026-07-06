from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QTimer, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.core.types import PageResult
from app.ui.theme import DANGER, TEXT

_FONT_FILTER = "Fonts (*.ttf *.otf *.ttc)"

_LOW_CONFIDENCE = 0.5  # below this, flag the region as worth double-checking
_AUTO_RERENDER_DELAY_MS = 500  # debounce so re-render doesn't fire on every keystroke


def _heading(text: str) -> QLabel:
    label = QLabel(text)
    label.setProperty("role", "heading")
    return label


class EditPanel(QWidget):
    """Manual correction: pick a detected region on the current page, edit its
    translated text, and re-render just the text layer (no re-OCR/translate/
    inpaint - see pipeline.rerender_page). Edits auto-apply a short moment
    after typing stops, so a forgotten click on "Re-render" no longer loses
    a correction."""

    rerender_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setMinimumWidth(240)
        self._result: PageResult | None = None
        self._loading = False

        self.region_list = QListWidget()
        self.source_view = QPlainTextEdit()
        self.source_view.setReadOnly(True)
        self.source_view.setMaximumHeight(70)
        self.translated_edit = QPlainTextEdit()
        self.translated_edit.setMaximumHeight(70)

        self.font_label = QLabel("Font: Default")
        self.font_choose_button = QPushButton("Choose...")
        self.font_choose_button.setEnabled(False)
        self.font_choose_button.clicked.connect(self._choose_font)
        self.font_clear_button = QPushButton("Default")
        self.font_clear_button.setEnabled(False)
        self.font_clear_button.clicked.connect(self._clear_font)
        font_row = QHBoxLayout()
        font_row.setSpacing(8)
        font_row.addWidget(self.font_choose_button)
        font_row.addWidget(self.font_clear_button)
        font_row.addStretch()

        self.rerender_button = QPushButton("Re-render this box")
        self.rerender_button.setProperty("role", "primary")
        self.rerender_button.setEnabled(False)

        self._auto_rerender_timer = QTimer(self)
        self._auto_rerender_timer.setSingleShot(True)
        self._auto_rerender_timer.setInterval(_AUTO_RERENDER_DELAY_MS)
        self._auto_rerender_timer.timeout.connect(self.rerender_requested.emit)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(8)
        layout.addWidget(_heading("Detected Text Boxes"))
        layout.addWidget(self.region_list, stretch=1)
        layout.addSpacing(4)
        layout.addWidget(_heading("Source (OCR)"))
        layout.addWidget(self.source_view)
        layout.addWidget(_heading("Translation (editable)"))
        layout.addWidget(self.translated_edit)
        layout.addWidget(self.font_label)
        layout.addLayout(font_row)
        layout.addWidget(self.rerender_button)

        self.region_list.currentRowChanged.connect(self._on_region_selected)
        self.translated_edit.textChanged.connect(self._on_text_edited)

    def set_page_result(self, result: PageResult | None) -> None:
        self._result = result
        self.region_list.clear()
        self._set_text_silently("")
        self.source_view.setPlainText("")
        self.rerender_button.setEnabled(False)

        if result is None:
            return

        for i, region in enumerate(result.regions):
            raw = (region.source_text or "").strip().replace("\n", " ")
            preview = raw[:30].rstrip() + "…" if len(raw) > 30 else raw
            low_confidence = not raw or region.confidence < _LOW_CONFIDENCE
            label = f"[{i}] {preview}" if preview else f"[{i}] (empty)"
            item = QListWidgetItem(f"⚠ {label}" if low_confidence else label)
            if low_confidence:
                item.setForeground(QColor(DANGER))
                item.setToolTip(f"Low OCR confidence ({region.confidence:.0%}) - worth double-checking")
            elif raw:
                item.setForeground(QColor(TEXT))
                item.setToolTip(raw)
            self.region_list.addItem(item)

    def _on_region_selected(self, row: int) -> None:
        self._auto_rerender_timer.stop()
        if self._result is None or row < 0 or row >= len(self._result.regions):
            self.rerender_button.setEnabled(False)
            self.font_choose_button.setEnabled(False)
            self.font_clear_button.setEnabled(False)
            self.font_label.setText("Font: Default")
            return
        region = self._result.regions[row]
        self.source_view.setPlainText(region.source_text)
        self._set_text_silently(region.translated_text)
        self.rerender_button.setEnabled(True)
        self.font_choose_button.setEnabled(True)
        self.font_clear_button.setEnabled(True)
        self._refresh_font_label(region)

    def _on_text_edited(self) -> None:
        if self._loading or not self.rerender_button.isEnabled():
            return
        self._auto_rerender_timer.start()

    def _refresh_font_label(self, region) -> None:
        name = Path(region.custom_font_path).name if region.custom_font_path else "Default"
        self.font_label.setText(f"Font: {name}")

    def _choose_font(self) -> None:
        row = self.current_region_index()
        if self._result is None or row < 0 or row >= len(self._result.regions):
            return
        path, _ = QFileDialog.getOpenFileName(self, "Choose Font for This Box", "", _FONT_FILTER)
        if path:
            self._result.regions[row].custom_font_path = path
            self._refresh_font_label(self._result.regions[row])
            self.rerender_requested.emit()

    def _clear_font(self) -> None:
        row = self.current_region_index()
        if self._result is None or row < 0 or row >= len(self._result.regions):
            return
        self._result.regions[row].custom_font_path = ""
        self._refresh_font_label(self._result.regions[row])
        self.rerender_requested.emit()

    def _set_text_silently(self, text: str) -> None:
        # setPlainText() fires textChanged too, which would otherwise queue an
        # auto-rerender for text the user never actually typed.
        self._loading = True
        self.translated_edit.setPlainText(text)
        self._loading = False

    def current_region_index(self) -> int:
        return self.region_list.currentRow()

    def edited_text(self) -> str:
        return self.translated_edit.toPlainText()
