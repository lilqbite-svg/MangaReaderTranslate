from __future__ import annotations

import numpy as np

from app.core.langs import get as get_lang


class OcrEngine:
    """Dispatches a crop to the right OCR backend based on source language:
    manga-ocr for Japanese (fine-tuned on manga dialogue), RapidOCR for the
    other ~39 languages (routed by script_group). `backend_overrides` lets a
    caller force a specific backend for a given ui_code, e.g. to use RapidOCR
    for Japanese instead of manga-ocr.
    """

    def __init__(self, backend_overrides: dict[str, str] | None = None) -> None:
        self._manga_ocr = None
        self._rapid_ocr = None
        self._overrides = backend_overrides or {}

    def recognize(self, crop: np.ndarray, src_lang: str) -> tuple[str, float]:
        """Returns (text, confidence). manga-ocr doesn't report a confidence
        score, so it's always 1.0 there; RapidOCR's is the mean per-line
        score, or 0.0 if it found nothing."""
        backend = self._overrides.get(src_lang, "manga_ocr" if src_lang == "ja" else "rapidocr")

        if backend == "manga_ocr":
            if self._manga_ocr is None:
                from app.core.ocr_manga import MangaOcr

                self._manga_ocr = MangaOcr()
            return self._manga_ocr.recognize(crop), 1.0

        if backend == "rapidocr":
            if self._rapid_ocr is None:
                from app.core.ocr_rapid import RapidOcr

                self._rapid_ocr = RapidOcr()
            script_group = get_lang(src_lang).script_group
            return self._rapid_ocr.recognize(crop, script_group)

        raise ValueError(f"Unknown OCR backend {backend!r} for {src_lang!r}")
