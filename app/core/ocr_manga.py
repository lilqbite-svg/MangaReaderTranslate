from __future__ import annotations

import numpy as np
from PIL import Image


class MangaOcr:
    """Wraps the `manga-ocr` package (kha-white/manga-ocr-base), fine-tuned for
    reading whole manga dialogue crops (vertical text, stylized fonts, furigana)."""

    def __init__(self) -> None:
        from manga_ocr import MangaOcr as _MangaOcr

        self._model = _MangaOcr()

    def recognize(self, crop: np.ndarray) -> str:
        """crop: HxWx3 RGB uint8 image of a single text region."""
        image = Image.fromarray(crop)
        return self._model(image).strip()
