from __future__ import annotations

import numpy as np

from app.core.types import TextRegion

# Unicode block -> ui_code, checked in order (kana/hangul before the wider
# CJK ideograph range so Japanese/Korean aren't misread as Chinese).
_RANGE_TO_LANG: list[tuple[tuple[int, int], str]] = [
    ((0x3040, 0x30FF), "ja"),  # Hiragana + Katakana
    ((0xAC00, 0xD7A3), "ko"),  # Hangul syllables
    ((0x4E00, 0x9FFF), "zh-Hans"),  # CJK Unified Ideographs
    ((0x0400, 0x04FF), "ru"),  # Cyrillic
    ((0x0370, 0x03FF), "el"),  # Greek
    ((0x0600, 0x06FF), "ar"),  # Arabic
    ((0x0900, 0x097F), "hi"),  # Devanagari
    ((0x0E00, 0x0E7F), "th"),  # Thai
]


def _classify_text(text: str) -> str | None:
    counts: dict[str, int] = {}
    for ch in text:
        cp = ord(ch)
        if cp < 0x80:
            continue  # plain ASCII doesn't distinguish among Latin-script languages
        for (lo, hi), lang in _RANGE_TO_LANG:
            if lo <= cp <= hi:
                counts[lang] = counts.get(lang, 0) + 1
                break
    if not counts:
        return None
    return max(counts, key=counts.get)


def detect_source_language(image: np.ndarray, regions: list[TextRegion], sample_count: int = 3) -> str:
    """Best-effort source-language guess from the first few detected regions:
    reads them with RapidOCR's broad default recognition model and sniffs the
    Unicode ranges of the output. Reliably distinguishes ja/ko/zh/ru/el/ar/hi/th;
    everything else (including a blank/garbled read, which is expected for
    scripts that model wasn't trained on) falls back to "en". This is a
    heuristic, not a real language-ID model - always let the user override it.
    """
    from app.core.ocr_rapid import RapidOcr

    reader = RapidOcr()
    combined_text = ""
    for region in regions[:sample_count]:
        x1, y1, x2, y2 = region.bbox
        crop = image[y1:y2, x1:x2]
        try:
            combined_text += reader.recognize(crop, "cjk_zh")
        except Exception:
            continue

    return _classify_text(combined_text) or "en"
