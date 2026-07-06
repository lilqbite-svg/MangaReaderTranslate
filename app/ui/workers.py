from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, QThread, Signal

from app.core.pipeline import Pipeline
from app.core.types import PageResult


class TranslationWorker(QObject):
    progress = Signal(int, int)  # current, total
    page_done = Signal(int, object)  # index, PageResult
    status = Signal(str)
    error = Signal(int, str)  # index, message
    finished = Signal()

    def __init__(
        self,
        image_paths: list[Path],
        src_lang: str,
        tgt_lang: str,
        device: str = "auto",
        ocr_backend_overrides: dict[str, str] | None = None,
        font_overrides: list[str] | None = None,
    ) -> None:
        super().__init__()
        self._image_paths = image_paths
        self._src_lang = src_lang
        self._tgt_lang = tgt_lang
        self._device = device
        self._ocr_backend_overrides = ocr_backend_overrides
        # Parallel to image_paths - one default font path per page (empty
        # string = no override), not a dict keyed by page index, so it stays
        # aligned even when this worker is only processing a subset of pages
        # (e.g. "Translate This Page").
        self._font_overrides = font_overrides or ([""] * len(image_paths))
        self._cancelled = False
        self.pipeline: Pipeline | None = None

    def cancel(self) -> None:
        self._cancelled = True

    def run(self) -> None:
        try:
            self.status.emit("Loading models (first run may take a while)...")
            pipeline = Pipeline(
                device=self._device,
                ocr_backend_overrides=self._ocr_backend_overrides,
                status_callback=self.status.emit,
            )
            self.pipeline = pipeline
        except Exception as exc:  # model load failure shouldn't crash the UI thread
            self.error.emit(-1, f"Failed to load models: {exc}")
            self.finished.emit()
            return

        total = len(self._image_paths)
        for i, path in enumerate(self._image_paths):
            if self._cancelled:
                break
            self.status.emit(f"Translating {path.name} ({i + 1}/{total})...")
            try:
                result = pipeline.process_page(
                    path, self._src_lang, self._tgt_lang, font_override=self._font_overrides[i]
                )
            except Exception as exc:
                self.error.emit(i, f"Failed on {path.name}: {exc}")
                continue
            self.page_done.emit(i, result)
            self.progress.emit(i + 1, total)

        self.status.emit("Done.")
        self.finished.emit()


def start_translation(
    image_paths: list[Path],
    src_lang: str,
    tgt_lang: str,
    device: str,
    on_progress,
    on_page_done,
    on_status,
    on_error,
    on_finished,
    ocr_backend_overrides: dict[str, str] | None = None,
    font_overrides: list[str] | None = None,
) -> tuple[QThread, TranslationWorker]:
    thread = QThread()
    worker = TranslationWorker(image_paths, src_lang, tgt_lang, device, ocr_backend_overrides, font_overrides)
    worker.moveToThread(thread)

    thread.started.connect(worker.run)
    worker.progress.connect(on_progress)
    worker.page_done.connect(on_page_done)
    worker.status.connect(on_status)
    worker.error.connect(on_error)
    worker.finished.connect(on_finished)
    worker.finished.connect(thread.quit)
    worker.finished.connect(worker.deleteLater)
    thread.finished.connect(thread.deleteLater)

    thread.start()
    return thread, worker
