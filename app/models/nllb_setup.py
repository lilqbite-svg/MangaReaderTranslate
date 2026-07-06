from __future__ import annotations

from pathlib import Path
from typing import Callable

import requests
from tqdm import tqdm

from app.models.manager import CACHE_ROOT, NLLB_HF_LOCAL_DIR

NLLB_CT2_DIR = CACHE_ROOT / "translate" / "nllb-200-distilled-600M-ct2"

_HF_REPO = "facebook/nllb-200-distilled-600M"
# Matches the file list from the README's old manual curl instructions -
# everything TransformersConverter needs from a local HF snapshot.
_HF_FILES = [
    "config.json",
    "generation_config.json",
    "pytorch_model.bin",
    "sentencepiece.bpe.model",
    "special_tokens_map.json",
    "tokenizer.json",
    "tokenizer_config.json",
]

StatusCallback = Callable[[str], None]

_PROGRESS_STEP_BYTES = 10_000_000  # ~10MB between UI status updates, not every 1MB chunk


def _download_with_resume(url: str, target: Path, status_callback: StatusCallback | None) -> None:
    """Downloads to `target`, resuming from `target.part` if a previous
    attempt was interrupted (HTTP Range) - the 600M model's pytorch_model.bin
    alone is over 1GB, so restarting from zero after a dropped connection
    isn't acceptable."""
    part_path = target.with_suffix(target.suffix + ".part")
    existing = part_path.stat().st_size if part_path.exists() else 0

    headers = {"Range": f"bytes={existing}-"} if existing else {}
    with requests.get(url, headers=headers, stream=True, timeout=60) as response:
        if response.status_code == 416:
            # Range not satisfiable - the .part file already has everything.
            part_path.rename(target)
            return
        response.raise_for_status()
        resumed = response.status_code == 206
        if not resumed:
            existing = 0
        total = existing + int(response.headers.get("content-length", 0))

        downloaded = existing
        last_reported = downloaded
        with open(part_path, "ab" if resumed else "wb") as f, tqdm(
            total=total, initial=existing, unit="B", unit_scale=True, desc=target.name
        ) as bar:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                f.write(chunk)
                downloaded += len(chunk)
                bar.update(len(chunk))
                if status_callback and downloaded - last_reported >= _PROGRESS_STEP_BYTES:
                    last_reported = downloaded
                    status_callback(
                        f"Downloading translation model: {target.name} "
                        f"({downloaded / 1e6:.0f}/{total / 1e6:.0f} MB)..."
                    )
    part_path.rename(target)


def ensure_nllb_ct2(status_callback: StatusCallback | None = None) -> Path:
    """Downloads facebook/nllb-200-distilled-600M's HF files (resuming any
    partial download across restarts) and converts them to a CTranslate2 int8
    model, unless that conversion is already cached. Only does real work on
    first use - later calls are a fast no-op - so it's safe to call from
    every Pipeline construction rather than needing a separate setup step."""
    if NLLB_CT2_DIR.exists() and any(NLLB_CT2_DIR.iterdir()):
        return NLLB_CT2_DIR

    NLLB_HF_LOCAL_DIR.mkdir(parents=True, exist_ok=True)
    for filename in _HF_FILES:
        target = NLLB_HF_LOCAL_DIR / filename
        if target.exists():
            continue
        if status_callback:
            status_callback(f"Downloading translation model: {filename}...")
        url = f"https://huggingface.co/{_HF_REPO}/resolve/main/{filename}"
        _download_with_resume(url, target, status_callback)

    if status_callback:
        status_callback("Converting translation model (one-time, ~1 minute)...")
    from ctranslate2.converters import TransformersConverter

    NLLB_CT2_DIR.parent.mkdir(parents=True, exist_ok=True)
    converter = TransformersConverter(str(NLLB_HF_LOCAL_DIR))
    converter.convert(str(NLLB_CT2_DIR), quantization="int8")
    return NLLB_CT2_DIR
