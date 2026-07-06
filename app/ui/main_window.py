from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QSplitter,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from app.config import get_settings
from app.core.langs import LANGUAGES
from app.core.pipeline import rerender_page
from app.core.types import PageResult
from app.io.exporters import save_cbz, save_images
from app.io.importers import load_pages
from app.io.session import clear_session, has_saved_session, load_session, save_session
from app.ui.batch_panel import BatchPanel
from app.ui.edit_panel import EditPanel
from app.ui.page_viewer import PageViewer
from app.ui.settings_dialog import (
    SettingsDialog,
    get_device_preference,
    get_global_font_path,
    get_ocr_backend_overrides,
    get_reading_mode,
)
from app.ui.workers import start_translation

_IMAGE_FILTER = "Images (*.jpg *.jpeg *.png *.webp *.bmp)"


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("MangaReaderTranslate")
        self.setAcceptDrops(True)

        self._settings = get_settings()
        self.resize(int(self._settings.value("window_w", 1150)), int(self._settings.value("window_h", 800)))

        self._image_paths: list[Path] = []
        self._results: dict[int, PageResult] = {}
        self._page_font_overrides: dict[int, str] = {}
        self._thread = None
        self._worker = None

        self.page_viewer = PageViewer()
        self.batch_panel = BatchPanel()
        self.edit_panel = EditPanel()
        self.page_viewer.set_reading_mode(get_reading_mode())

        self.src_combo = QComboBox()
        self.tgt_combo = QComboBox()
        self.src_combo.addItem("Auto-detect", "auto")
        for lang in LANGUAGES.values():
            self.src_combo.addItem(lang.display_name, lang.ui_code)
            self.tgt_combo.addItem(lang.display_name, lang.ui_code)
        self._restore_combo(self.src_combo, "src_lang", "ja")
        self._restore_combo(self.tgt_combo, "tgt_lang", "en")

        self.status_label = QLabel("Open an image, folder, or CBZ to begin.")
        self.status_label.setProperty("role", "status")

        self.src_combo.setMinimumWidth(160)
        self.tgt_combo.setMinimumWidth(160)

        from_label = QLabel("From")
        from_label.setProperty("role", "heading")
        to_label = QLabel("To")
        to_label.setProperty("role", "heading")

        top_bar = QWidget()
        top_bar.setObjectName("TopBar")
        top_layout = QHBoxLayout(top_bar)
        top_layout.setContentsMargins(16, 12, 16, 12)
        top_layout.setSpacing(10)
        top_layout.addWidget(from_label)
        top_layout.addWidget(self.src_combo)
        top_layout.addSpacing(12)
        top_layout.addWidget(to_label)
        top_layout.addWidget(self.tgt_combo)
        top_layout.addStretch()

        self.batch_panel.setObjectName("SidePanel")
        self.edit_panel.setObjectName("SidePanel")

        splitter = QSplitter()
        splitter.setHandleWidth(2)
        splitter.addWidget(self.batch_panel)
        splitter.addWidget(self.page_viewer)
        splitter.addWidget(self.edit_panel)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 0)
        splitter.setSizes([240, 700, 280])

        central = QWidget()
        central_layout = QVBoxLayout(central)
        central_layout.setContentsMargins(0, 0, 0, 0)
        central_layout.setSpacing(0)
        central_layout.addWidget(top_bar)
        central_layout.addWidget(splitter, stretch=1)
        self.setCentralWidget(central)

        status_bar = self.statusBar()
        status_bar.addWidget(self.status_label, stretch=1)

        self._build_toolbar()
        self._build_menu()
        self._build_shortcuts()

        self.batch_panel.list_widget.currentRowChanged.connect(self._on_page_selected)
        self.batch_panel.start_button.clicked.connect(self._start_translation)
        self.batch_panel.cancel_button.clicked.connect(self._cancel_translation)
        self.batch_panel.translate_page_button.clicked.connect(self._translate_current_page)
        self.batch_panel.pages_reordered.connect(self._on_pages_reordered)
        self.batch_panel.page_font_chosen.connect(self._on_page_font_chosen)
        self.edit_panel.rerender_button.clicked.connect(self._rerender_current_region)
        self.edit_panel.rerender_requested.connect(self._rerender_current_region)
        self.page_viewer.region_selected.connect(self._on_region_selected_in_viewer)
        self.page_viewer.prev_requested.connect(self._prev_page)
        self.page_viewer.next_requested.connect(self._next_page)
        self.edit_panel.region_list.currentRowChanged.connect(self._on_region_selected_in_list)

        # Deferred to the next event loop tick: this runs at the end of
        # __init__, before main.py has called window.show(), so selecting a
        # restored page here immediately would hit page_viewer.reset_zoom()
        # while the view is still an unlaid-out 0x0 widget.
        QTimer.singleShot(0, self._maybe_restore_session)

    def _restore_combo(self, combo: QComboBox, key: str, default_code: str) -> None:
        code = self._settings.value(key, default_code)
        self._select_combo_data(combo, code)

    def _select_combo_data(self, combo: QComboBox, code: str) -> None:
        index = combo.findData(code)
        combo.setCurrentIndex(index if index >= 0 else 0)

    def _build_toolbar(self) -> None:
        toolbar = QToolBar("Main")
        toolbar.setMovable(False)
        toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        toolbar.setIconSize(toolbar.iconSize())
        self.addToolBar(toolbar)

        open_action = toolbar.addAction("Open")
        open_action.setShortcut(QKeySequence.StandardKey.Open)
        open_action.triggered.connect(self._open_image)

        add_action = toolbar.addAction("Add Pages")
        add_action.triggered.connect(self._add_images)

        export_action = toolbar.addAction("Export")
        export_action.setShortcut(QKeySequence("Ctrl+E"))
        export_action.triggered.connect(self._export_images)

        toolbar.addSeparator()

        settings_action = toolbar.addAction("Settings")
        settings_action.triggered.connect(self._open_settings)

    def _build_menu(self) -> None:
        menu = self.menuBar().addMenu("&File")

        open_image = menu.addAction("Open Image...")
        open_image.triggered.connect(self._open_image)

        open_folder = menu.addAction("Open Folder...")
        open_folder.triggered.connect(self._open_folder)

        open_cbz = menu.addAction("Open CBZ/ZIP...")
        open_cbz.triggered.connect(self._open_cbz)

        menu.addSeparator()

        add_images = menu.addAction("Add Image(s)...")
        add_images.setToolTip("Append one or more pages to what's already loaded, instead of replacing it")
        add_images.triggered.connect(self._add_images)

        add_folder = menu.addAction("Add Folder...")
        add_folder.triggered.connect(self._add_folder)

        add_cbz = menu.addAction("Add CBZ/ZIP...")
        add_cbz.triggered.connect(self._add_cbz)

        menu.addSeparator()

        export_images = menu.addAction("Export as Images...")
        export_images.triggered.connect(self._export_images)

        export_cbz = menu.addAction("Export as CBZ...")
        export_cbz.triggered.connect(self._export_cbz)

        settings_menu = self.menuBar().addMenu("&Settings")
        open_settings = settings_menu.addAction("Preferences...")
        open_settings.triggered.connect(self._open_settings)

    def _build_shortcuts(self) -> None:
        fit_shortcut = QShortcut(QKeySequence("Ctrl+0"), self)
        fit_shortcut.activated.connect(self.page_viewer.reset_zoom)

        # Left/Right work from either the page list or the page viewer. Up/
        # Down are scoped to the page viewer only - QListWidget already uses
        # Up/Down natively to move the highlighted row, and layering another
        # shortcut for the same keys on that widget would fight it.
        self._add_navigation_shortcut(Qt.Key.Key_Left, self._prev_page)
        self._add_navigation_shortcut(Qt.Key.Key_Right, self._next_page)
        self._add_navigation_shortcut(Qt.Key.Key_Up, self._prev_page, widgets=(self.page_viewer,))
        self._add_navigation_shortcut(Qt.Key.Key_Down, self._next_page, widgets=(self.page_viewer,))
        self._add_navigation_shortcut(Qt.Key.Key_Space, self.page_viewer.toggle_view)

    def _add_navigation_shortcut(self, key: Qt.Key, slot, widgets=None) -> None:
        for widget in widgets or (self.batch_panel.list_widget, self.page_viewer):
            shortcut = QShortcut(QKeySequence(key), widget)
            shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            shortcut.activated.connect(slot)

    def _open_settings(self) -> None:
        SettingsDialog(self).exec()
        self.page_viewer.set_reading_mode(get_reading_mode())

    def _last_dir(self) -> str:
        return self._settings.value("last_dir", "")

    def _remember_dir(self, path: Path) -> None:
        directory = str(path if path.is_dir() else path.parent)
        self._settings.setValue("last_dir", directory)

    def _open_image(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Open Image", self._last_dir(), _IMAGE_FILTER)
        if path:
            self._remember_dir(Path(path))
            self._load_pages(Path(path))

    def _open_folder(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Open Folder", self._last_dir())
        if path:
            self._remember_dir(Path(path))
            self._load_pages(Path(path))

    def _open_cbz(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Open CBZ/ZIP", self._last_dir(), "Comic archives (*.cbz *.zip)"
        )
        if path:
            self._remember_dir(Path(path))
            self._load_pages(Path(path))

    def _add_images(self) -> None:
        # getOpenFileNames (plural) lets the user pick one file or ctrl/shift-
        # select many at once - "add one page or a batch" is the same dialog.
        paths, _ = QFileDialog.getOpenFileNames(self, "Add Image(s)", self._last_dir(), _IMAGE_FILTER)
        if paths:
            self._remember_dir(Path(paths[0]))
            self._append_pages([Path(p) for p in paths])

    def _add_folder(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Add Folder", self._last_dir())
        if path:
            self._remember_dir(Path(path))
            self._append_from_loader(Path(path))

    def _add_cbz(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Add CBZ/ZIP", self._last_dir(), "Comic archives (*.cbz *.zip)")
        if path:
            self._remember_dir(Path(path))
            self._append_from_loader(Path(path))

    def _append_from_loader(self, path: Path) -> None:
        try:
            new_paths = load_pages(path)
        except Exception as exc:
            QMessageBox.critical(self, "Failed to load", str(exc))
            return
        self._append_pages(new_paths)

    def _append_pages(self, new_paths: list[Path]) -> None:
        was_empty = not self._image_paths
        self._image_paths.extend(new_paths)
        self.batch_panel.add_pages(new_paths)
        self.status_label.setText(f"Added {len(new_paths)} page(s) - {len(self._image_paths)} total.")
        if was_empty and self._image_paths:
            self.batch_panel.list_widget.setCurrentRow(0)
        self._autosave()

    def dragEnterEvent(self, event) -> None:  # noqa: N802 (Qt override)
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:  # noqa: N802 (Qt override)
        # Appends (like Add Pages) rather than replaces (like Open): dropping
        # a new screenshot onto the app while pages are already loaded should
        # add it, not wipe out what's already there. If nothing was loaded
        # yet, appending to an empty list has the same end result as
        # replacing, so one code path covers both cases. Handles multiple
        # dropped files/folders too, not just the first.
        paths = [Path(u.toLocalFile()) for u in event.mimeData().urls()]
        paths = [p for p in paths if p.exists()]
        if not paths:
            return
        self._remember_dir(paths[0])
        for path in paths:
            self._append_from_loader(path)

    def _load_pages(self, path: Path) -> None:
        try:
            self._image_paths = load_pages(path)
        except Exception as exc:
            QMessageBox.critical(self, "Failed to load", str(exc))
            return

        self._results = {}
        self._page_font_overrides = {}
        self.batch_panel.set_pages(self._image_paths)
        self.batch_panel.set_progress(0, len(self._image_paths))
        self.status_label.setText(f"Loaded {len(self._image_paths)} page(s).")
        if self._image_paths:
            self.batch_panel.list_widget.setCurrentRow(0)

    def _on_page_selected(self, row: int) -> None:
        if row < 0 or row >= len(self._image_paths):
            return
        from PIL import Image
        import numpy as np

        image = np.array(Image.open(self._image_paths[row]).convert("RGB"))
        self.page_viewer.set_original(image)
        result = self._results.get(row)
        if result is not None:
            self.page_viewer.set_translated(result.output_image, result.regions)
        self.edit_panel.set_page_result(result)
        self.page_viewer.set_nav_enabled(row > 0, row < len(self._image_paths) - 1)

    def _on_region_selected_in_viewer(self, index: int) -> None:
        self.edit_panel.region_list.setCurrentRow(index)

    def _on_region_selected_in_list(self, row: int) -> None:
        self.page_viewer.set_selected_region(row if row >= 0 else None)

    def _on_pages_reordered(self) -> None:
        new_paths = self.batch_panel.paths_in_order()
        new_index_by_path = {path: i for i, path in enumerate(new_paths)}

        def _remap(old_dict: dict) -> dict:
            remapped = {}
            for old_i, value in old_dict.items():
                if old_i < len(self._image_paths):
                    new_i = new_index_by_path.get(self._image_paths[old_i])
                    if new_i is not None:
                        remapped[new_i] = value
            return remapped

        self._results = _remap(self._results)
        self._page_font_overrides = _remap(self._page_font_overrides)
        self._image_paths = new_paths
        self._autosave()

    def _on_page_font_chosen(self, row: int, font_path: str) -> None:
        if font_path:
            self._page_font_overrides[row] = font_path
        else:
            self._page_font_overrides.pop(row, None)
        self.status_label.setText(
            f"Font override {'set' if font_path else 'cleared'} for page {row + 1}."
        )

    def _effective_font_for_page(self, index: int) -> str:
        return self._page_font_overrides.get(index, "") or get_global_font_path()

    def _start_translation(self) -> None:
        if not self._image_paths:
            QMessageBox.information(self, "Nothing to translate", "Open an image, folder, or CBZ first.")
            return
        self._run_translation(list(enumerate(self._image_paths)))

    def _translate_current_page(self) -> None:
        row = self.batch_panel.list_widget.currentRow()
        if row < 0 or row >= len(self._image_paths):
            return
        self._run_translation([(row, self._image_paths[row])])

    def _run_translation(self, indexed_paths: list[tuple[int, Path]]) -> None:
        src_lang = self.src_combo.currentData()
        tgt_lang = self.tgt_combo.currentData()
        self._settings.setValue("src_lang", src_lang)
        self._settings.setValue("tgt_lang", tgt_lang)

        indices = [i for i, _ in indexed_paths]
        paths = [p for _, p in indexed_paths]
        font_overrides = [self._effective_font_for_page(i) for i in indices]
        for i in indices:
            self.batch_panel.mark_status(i, "running")

        self.batch_panel.set_running(True)
        self._thread, self._worker = start_translation(
            paths,
            src_lang,
            tgt_lang,
            get_device_preference(),
            on_progress=self.batch_panel.set_progress,
            on_page_done=lambda local_i, result: self._on_page_done(indices[local_i], result),
            on_status=self.status_label.setText,
            on_error=lambda local_i, msg: self._on_page_error(indices[local_i], msg),
            on_finished=self._on_translation_finished,
            ocr_backend_overrides=get_ocr_backend_overrides(),
            font_overrides=font_overrides,
        )

    def _on_translation_finished(self) -> None:
        self.batch_panel.set_running(False)
        self._autosave()

    def _rerender_current_region(self) -> None:
        row = self.batch_panel.list_widget.currentRow()
        result = self._results.get(row)
        if result is None:
            return
        region_index = self.edit_panel.current_region_index()
        if region_index < 0 or region_index >= len(result.regions):
            return

        result.regions[region_index].translated_text = self.edit_panel.edited_text()
        tgt = LANGUAGES[self.tgt_combo.currentData()]
        result.output_image = rerender_page(
            result.cleaned_image, result.regions, tgt.script_group,
            default_font_override=self._effective_font_for_page(row),
        )
        self.page_viewer.set_translated(result.output_image, result.regions)
        self._autosave()

    def _cancel_translation(self) -> None:
        if self._worker is not None:
            self._worker.cancel()

    def _on_page_done(self, index: int, result: PageResult) -> None:
        self._results[index] = result
        self.batch_panel.mark_status(index, "done")
        if self.batch_panel.list_widget.currentRow() == index:
            self.page_viewer.set_translated(result.output_image, result.regions)
            self.edit_panel.set_page_result(result)

    def _on_page_error(self, index: int, msg: str) -> None:
        if index >= 0:
            self.batch_panel.mark_status(index, "error")
        QMessageBox.warning(self, "Translation error", msg)

    def _prev_page(self) -> None:
        row = self.batch_panel.list_widget.currentRow()
        if row > 0:
            self.batch_panel.list_widget.setCurrentRow(row - 1)

    def _next_page(self) -> None:
        row = self.batch_panel.list_widget.currentRow()
        if row < self.batch_panel.list_widget.count() - 1:
            self.batch_panel.list_widget.setCurrentRow(row + 1)

    def _export_images(self) -> None:
        if not self._results:
            QMessageBox.information(self, "Nothing to export", "Translate at least one page first.")
            return
        out_dir = QFileDialog.getExistingDirectory(self, "Export Folder", self._last_dir())
        if out_dir:
            self._remember_dir(Path(out_dir))
            ordered = [self._results[i] for i in sorted(self._results)]
            save_images(ordered, Path(out_dir))
            QMessageBox.information(self, "Exported", f"Saved {len(ordered)} page(s) to {out_dir}")

    def _export_cbz(self) -> None:
        if not self._results:
            QMessageBox.information(self, "Nothing to export", "Translate at least one page first.")
            return
        out_path, _ = QFileDialog.getSaveFileName(
            self, "Export CBZ", str(Path(self._last_dir()) / "translated.cbz"), "Comic archive (*.cbz)"
        )
        if out_path:
            self._remember_dir(Path(out_path))
            ordered = [self._results[i] for i in sorted(self._results)]
            save_cbz(ordered, Path(out_path))
            QMessageBox.information(self, "Exported", f"Saved {len(ordered)} page(s) to {out_path}")

    def _autosave(self) -> None:
        if self._results:
            save_session(self._image_paths, self._results, self.src_combo.currentData(), self.tgt_combo.currentData())

    def _maybe_restore_session(self) -> None:
        if not has_saved_session():
            return
        reply = QMessageBox.question(
            self,
            "Restore previous session?",
            "Found an autosaved session from your last run (translated pages and any manual "
            "edits). Restore it?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            clear_session()
            return

        try:
            image_paths, results, src_lang, tgt_lang = load_session()
        except Exception as exc:
            QMessageBox.warning(self, "Restore failed", f"Could not restore the previous session: {exc}")
            clear_session()
            return

        self._image_paths = image_paths
        self._results = results
        self.batch_panel.set_pages(image_paths)
        self.batch_panel.set_progress(len(results), len(image_paths))
        for i in range(len(image_paths)):
            if i in results:
                self.batch_panel.mark_status(i, "done")
        self._select_combo_data(self.src_combo, src_lang)
        self._select_combo_data(self.tgt_combo, tgt_lang)
        self.status_label.setText(f"Restored {len(results)}/{len(image_paths)} translated page(s) from last session.")
        if image_paths:
            self.batch_panel.list_widget.setCurrentRow(0)

    def closeEvent(self, event) -> None:  # noqa: N802 (Qt override)
        self._settings.setValue("window_w", self.width())
        self._settings.setValue("window_h", self.height())
        self._autosave()
        super().closeEvent(event)
