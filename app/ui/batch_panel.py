from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QColor, QIcon, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.ui.theme import ACCENT, DANGER, TEXT, TEXT_DIM

_THUMB_SIZE = QSize(44, 58)
_PATH_ROLE = Qt.ItemDataRole.UserRole
_FONT_FILTER = "Fonts (*.ttf *.otf *.ttc)"

_STATUS_STYLE = {
    "queued": ("", TEXT),
    "running": ("▸ ", ACCENT),  # small right-pointing triangle
    "done": ("✓ ", TEXT),  # check mark
    "error": ("✗ ", DANGER),  # cross mark
}


def _thumbnail(path: Path) -> QIcon:
    pixmap = QPixmap(str(path))
    if pixmap.isNull():
        return QIcon()
    scaled = pixmap.scaled(_THUMB_SIZE, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
    return QIcon(scaled)


def _make_item(path: Path) -> QListWidgetItem:
    item = QListWidgetItem(_thumbnail(path), path.name)
    item.setData(_PATH_ROLE, str(path))
    return item


class BatchPanel(QWidget):
    """Page list + progress bar + start/cancel controls for batch-translating
    a whole chapter. Pages can be added incrementally (not just replaced by
    a fresh Open), dragged to reorder, multi-selected and removed (right-click
    or the Remove buttons), and given a per-page font override via the
    right-click menu."""

    pages_reordered = Signal()  # also emitted after removals - anything that
    # changes which pages exist or their order, since MainWindow resyncs its
    # index-keyed state (_results, _page_font_overrides) from paths_in_order()
    # either way.
    page_font_chosen = Signal(int, str)  # row, font_path ("" clears the override)

    def __init__(self) -> None:
        super().__init__()
        self.setMinimumWidth(220)

        heading = QLabel("Pages")
        heading.setProperty("role", "heading")

        self.list_widget = QListWidget()
        self.list_widget.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.list_widget.setIconSize(_THUMB_SIZE)
        # Lets the user drag list rows to reorder pages before/while translating.
        self.list_widget.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.list_widget.model().rowsMoved.connect(lambda *_: self.pages_reordered.emit())
        self.list_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list_widget.customContextMenuRequested.connect(self._show_context_menu)

        self._statuses: list[str] = []

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)

        self.start_button = QPushButton("Translate All")
        self.start_button.setProperty("role", "primary")
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setEnabled(False)
        self.translate_page_button = QPushButton("Translate This Page")
        self.translate_page_button.setEnabled(False)

        self.remove_selected_button = QPushButton("Remove Selected")
        self.remove_selected_button.setEnabled(False)
        self.remove_selected_button.clicked.connect(self._remove_selected)
        self.remove_all_button = QPushButton("Remove All")
        self.remove_all_button.setProperty("role", "danger")
        self.remove_all_button.setEnabled(False)
        self.remove_all_button.clicked.connect(self._remove_all)

        button_row = QHBoxLayout()
        button_row.setSpacing(8)
        button_row.addWidget(self.start_button, stretch=1)
        button_row.addWidget(self.cancel_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)
        layout.addWidget(heading)
        layout.addWidget(self.list_widget, stretch=1)
        # Full-width, stacked rather than side-by-side: this panel is narrow
        # enough that "Remove Selected" + "Remove All" sharing one row left
        # neither with enough width for its label, and QPushButton just
        # clips overflowing text instead of eliding it with "...".
        layout.addWidget(self.remove_selected_button)
        layout.addWidget(self.remove_all_button)
        layout.addLayout(button_row)
        layout.addWidget(self.translate_page_button)
        layout.addWidget(self.progress_bar)

        self.list_widget.currentRowChanged.connect(self._on_selection_changed)
        self.list_widget.itemSelectionChanged.connect(self._on_item_selection_changed)

    def set_pages(self, paths: list[Path]) -> None:
        self.list_widget.clear()
        self._statuses = ["queued"] * len(paths)
        for path in paths:
            self.list_widget.addItem(_make_item(path))
        self.translate_page_button.setEnabled(bool(paths))
        self.remove_all_button.setEnabled(bool(paths))

    def add_pages(self, paths: list[Path]) -> None:
        """Appends pages to whatever's already loaded, instead of replacing
        the list - for "add more pages/a folder/a CBZ to what I already have"
        rather than starting a fresh batch."""
        self._statuses.extend(["queued"] * len(paths))
        for path in paths:
            self.list_widget.addItem(_make_item(path))
        self.translate_page_button.setEnabled(self.list_widget.count() > 0)
        self.remove_all_button.setEnabled(self.list_widget.count() > 0)

    def paths_in_order(self) -> list[Path]:
        """Current visual order of pages, e.g. after a drag-to-reorder."""
        return [Path(self.list_widget.item(i).data(_PATH_ROLE)) for i in range(self.list_widget.count())]

    def mark_status(self, index: int, status: str) -> None:
        if not (0 <= index < self.list_widget.count()):
            return
        if index >= len(self._statuses):
            self._statuses.extend(["queued"] * (index + 1 - len(self._statuses)))
        self._statuses[index] = status
        item = self.list_widget.item(index)
        if item is None:
            return
        prefix, color = _STATUS_STYLE[status]
        name = Path(item.data(_PATH_ROLE)).name
        item.setText(f"{prefix}{name}")
        item.setForeground(QColor(color))

    def mark_done(self, index: int) -> None:
        self.mark_status(index, "done")

    def set_progress(self, current: int, total: int) -> None:
        self.progress_bar.setMaximum(max(total, 1))
        self.progress_bar.setValue(current)

    def set_running(self, running: bool) -> None:
        self.start_button.setEnabled(not running)
        self.cancel_button.setEnabled(running)
        self.translate_page_button.setEnabled(not running and self.list_widget.count() > 0)

    def _on_selection_changed(self, row: int) -> None:
        self.translate_page_button.setEnabled(
            row >= 0 and self.start_button.isEnabled() and self.list_widget.count() > 0
        )

    def _on_item_selection_changed(self) -> None:
        self.remove_selected_button.setEnabled(bool(self.list_widget.selectedItems()))

    def _remove_selected(self) -> None:
        rows = sorted((self.list_widget.row(item) for item in self.list_widget.selectedItems()), reverse=True)
        if not rows:
            return
        reply = QMessageBox.question(
            self,
            "Remove page(s)?",
            f"Remove {len(rows)} page(s) from this session? The original files on disk aren't affected.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        for row in rows:
            self.list_widget.takeItem(row)
        self.translate_page_button.setEnabled(self.list_widget.count() > 0)
        self.remove_all_button.setEnabled(self.list_widget.count() > 0)
        self.pages_reordered.emit()

    def _remove_all(self) -> None:
        if self.list_widget.count() == 0:
            return
        reply = QMessageBox.question(
            self,
            "Remove all pages?",
            f"Remove all {self.list_widget.count()} page(s) from this session? The original files "
            "on disk aren't affected, but any translations not yet exported will be lost.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        self.list_widget.clear()
        self._statuses = []
        self.translate_page_button.setEnabled(False)
        self.remove_all_button.setEnabled(False)
        self.remove_selected_button.setEnabled(False)
        self.pages_reordered.emit()

    def _show_context_menu(self, pos) -> None:
        clicked_item = self.list_widget.itemAt(pos)
        if clicked_item is not None and clicked_item not in self.list_widget.selectedItems():
            # Right-clicking outside the current multi-selection acts like a
            # plain click first, matching typical file-manager behavior.
            self.list_widget.setCurrentItem(clicked_item)
        row = self.list_widget.currentRow()

        menu = QMenu(self)
        selected_count = len(self.list_widget.selectedItems())
        remove_action = None
        set_font_action = None
        clear_font_action = None
        if selected_count:
            remove_label = "Remove Selected Page" if selected_count == 1 else f"Remove {selected_count} Pages"
            remove_action = menu.addAction(remove_label)
            menu.addSeparator()
        if row >= 0:
            set_font_action = menu.addAction("Set Font for This Page...")
            clear_font_action = menu.addAction("Use Default Font for This Page")

        action = menu.exec(self.list_widget.viewport().mapToGlobal(pos))
        if action is None:
            return
        if action == remove_action:
            self._remove_selected()
        elif action == set_font_action:
            path, _ = QFileDialog.getOpenFileName(self, "Choose Font for This Page", "", _FONT_FILTER)
            if path:
                self.page_font_chosen.emit(row, path)
        elif action == clear_font_action:
            self.page_font_chosen.emit(row, "")
