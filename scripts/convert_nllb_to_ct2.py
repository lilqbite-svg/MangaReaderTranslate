"""One-time conversion: facebook/nllb-200-distilled-600M (HF/PyTorch) -> CTranslate2 int8.

Run once after installing requirements.txt:
    python scripts/convert_nllb_to_ct2.py

Produces the model directory consumed by app.core.translator.NLLBTranslator at
%LOCALAPPDATA%\\MangaReaderTranslate\\models\\translate\\nllb-200-distilled-600M-ct2
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ctranslate2.converters import TransformersConverter

from app.models.manager import CACHE_ROOT, NLLB_HF_LOCAL_DIR

OUTPUT_DIR = CACHE_ROOT / "translate" / "nllb-200-distilled-600M-ct2"

REQUIRED_FILES = ["config.json", "pytorch_model.bin", "sentencepiece.bpe.model", "tokenizer.json"]


def main() -> None:
    if OUTPUT_DIR.exists() and any(OUTPUT_DIR.iterdir()):
        print(f"Already converted at {OUTPUT_DIR}, skipping. Delete the folder to reconvert.")
        return

    missing = [f for f in REQUIRED_FILES if not (NLLB_HF_LOCAL_DIR / f).exists()]
    if missing:
        raise RuntimeError(
            f"Missing NLLB files in {NLLB_HF_LOCAL_DIR}: {missing}. "
            "Download facebook/nllb-200-distilled-600M's files there first "
            "(see README) before running this script."
        )

    OUTPUT_DIR.parent.mkdir(parents=True, exist_ok=True)
    print(f"Converting local snapshot {NLLB_HF_LOCAL_DIR} -> {OUTPUT_DIR} (int8)...")
    converter = TransformersConverter(str(NLLB_HF_LOCAL_DIR))
    converter.convert(str(OUTPUT_DIR), quantization="int8")
    print("Done.")


if __name__ == "__main__":
    main()
