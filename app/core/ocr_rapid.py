from __future__ import annotations

import numpy as np

# Maps our script_group (app/core/langs.py) to RapidOCR's LangRec enum member
# (PP-OCRv5 recognition models, richest language coverage as of writing).
# Scripts with no matching RapidOCR model (Hebrew, Bengali, Khmer) aren't
# wired up yet - raises a clear error rather than silently mis-recognizing.
_SCRIPT_TO_LANG_REC_NAME: dict[str, str] = {
    "latin": "LATIN",
    "cyrillic": "CYRILLIC",
    "greek": "EL",
    "arabic": "ARABIC",
    "devanagari": "DEVANAGARI",
    "tamil": "TA",
    "telugu": "TE",
    "thai": "TH",
    "cjk_ko": "KOREAN",
    "cjk_zh": "CH",
}


class RapidOcr:
    """Wraps RapidOCR (pure onnxruntime PP-OCR port, no PaddlePaddle) for the
    ~39 non-Japanese source languages. One engine instance per script_group,
    lazily created and cached, since each needs its own recognition model."""

    def __init__(self) -> None:
        self._engines: dict[str, object] = {}

    def _engine_for(self, script_group: str):
        if script_group not in _SCRIPT_TO_LANG_REC_NAME:
            raise NotImplementedError(
                f"RapidOCR has no recognition model wired up for script_group={script_group!r} yet."
            )
        if script_group not in self._engines:
            from rapidocr import LangRec, ModelType, OCRVersion, RapidOCR

            lang_type = LangRec[_SCRIPT_TO_LANG_REC_NAME[script_group]]
            # RapidOCR defaults to PP-OCRv6, whose recognition model only
            # supports lang_type=CH - the broader language set (latin,
            # cyrillic, arabic, devanagari, ta, te, th, el, korean, ...) is
            # only available on PP-OCRv5's mobile model.
            self._engines[script_group] = RapidOCR(
                params={
                    "Rec.lang_type": lang_type,
                    "Rec.ocr_version": OCRVersion.PPOCRV5,
                    "Rec.model_type": ModelType.MOBILE,
                }
            )
        return self._engines[script_group]

    def recognize(self, crop: np.ndarray, script_group: str) -> tuple[str, float]:
        """crop: HxWx3 RGB uint8 image of a single text region. Returns
        (text, confidence) - confidence is the mean of RapidOCR's per-line
        scores, or 1.0 if it returned no per-line scores at all."""
        engine = self._engine_for(script_group)
        result = engine(crop)
        if result is None or not result.txts:
            return "", 0.0
        scores = result.scores or []
        confidence = float(np.mean(scores)) if scores else 1.0
        return " ".join(result.txts), confidence
