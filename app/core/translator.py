from __future__ import annotations

from pathlib import Path
from typing import Protocol

import ctranslate2
from transformers import AutoTokenizer

from app.models.manager import NLLB_HF_LOCAL_DIR


class Translator(Protocol):
    def translate(self, texts: list[str], src_lang: str, tgt_lang: str) -> list[str]:
        ...


class NLLBTranslator:
    """Runs a CTranslate2-converted NLLB-200 model. `src_lang`/`tgt_lang` are
    NLLB/FLORES-200 codes, e.g. "jpn_Jpan", "eng_Latn" (see app/core/langs.py).
    """

    def __init__(self, ct2_model_dir: Path, device: str = "auto") -> None:
        resolved_device = device
        if device == "auto":
            resolved_device = "cuda" if ctranslate2.get_cuda_device_count() > 0 else "cpu"

        try:
            translator = ctranslate2.Translator(str(ct2_model_dir), device=resolved_device)
            # ctranslate2 loads its CUDA libraries (cuBLAS etc.) lazily on first
            # use, not at construction - a missing/mismatched CUDA runtime only
            # surfaces here, not above. Force that lazily-loaded path now so a
            # broken GPU setup falls back to CPU instead of crashing later.
            translator.translate_batch([["<pad>"]], target_prefix=[["eng_Latn"]])
            self._translator = translator
            self.device = resolved_device
        except Exception:
            self._translator = ctranslate2.Translator(str(ct2_model_dir), device="cpu")
            self.device = "cpu"

        self._tokenizer = AutoTokenizer.from_pretrained(str(NLLB_HF_LOCAL_DIR))

    def translate(self, texts: list[str], src_lang: str, tgt_lang: str) -> list[str]:
        if not texts:
            return []

        self._tokenizer.src_lang = src_lang
        sources = [
            self._tokenizer.convert_ids_to_tokens(self._tokenizer.encode(text)) for text in texts
        ]
        target_prefix = [[tgt_lang]] * len(sources)

        results = self._translator.translate_batch(sources, target_prefix=target_prefix)

        translations = []
        for result in results:
            output_tokens = result.hypotheses[0][1:]  # drop the forced target-lang token
            token_ids = self._tokenizer.convert_tokens_to_ids(output_tokens)
            translations.append(self._tokenizer.decode(token_ids, skip_special_tokens=True))
        return translations
