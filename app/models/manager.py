from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import requests
from tqdm import tqdm


def _default_cache_root() -> Path:
    local_appdata = os.environ.get("LOCALAPPDATA")
    base = Path(local_appdata) if local_appdata else Path.home() / ".cache"
    # Deliberately not "MangaReaderTranslate" - that exact folder name under
    # %LOCALAPPDATA% was mysteriously invisible (CreateFile: PATH NOT FOUND)
    # to the PyInstaller-frozen build specifically, even though it was
    # confirmed present via PowerShell/Explorer and the running process was a
    # normal, non-virtualized, Medium-integrity process. Renaming sidesteps
    # whatever that was rather than continuing to chase it blind.
    return base / "MRTranslateCache" / "models"


CACHE_ROOT = _default_cache_root()

# Local snapshot of facebook/nllb-200-distilled-600M (HF files fetched directly
# via curl with retry/resume rather than huggingface_hub's downloader, which
# proved unreliable on flaky connections). Both the conversion script and the
# translator's tokenizer load from here.
NLLB_HF_LOCAL_DIR = CACHE_ROOT / "translate" / "nllb-200-distilled-600M-hf"

ProgressCallback = Callable[[int, int], None]


@dataclass(frozen=True)
class ModelSpec:
    subdir: str
    filename: str
    url: str


# Phase 1 registry. manga-ocr manages its own HF download internally, and the
# NLLB CTranslate2 model is produced locally by scripts/convert_nllb_to_ct2.py,
# so neither needs an entry here.
REGISTRY: dict[str, ModelSpec] = {
    "comic_text_detector": ModelSpec(
        subdir="detector",
        filename="comictextdetector.pt.onnx",
        url="https://github.com/zyddnys/manga-image-translator/releases/download/beta-0.3/comictextdetector.pt.onnx",
    ),
    "lama_manga": ModelSpec(
        subdir="inpaint",
        filename="lama-manga-dynamic.onnx",
        url="https://huggingface.co/ogkalu/lama-manga-onnx-dynamic/resolve/main/lama-manga-dynamic.onnx",
    ),
}


class ModelManager:
    def __init__(self, cache_root: Path | None = None) -> None:
        self.cache_root = cache_root or CACHE_ROOT

    def path_for(self, model_id: str) -> Path:
        spec = REGISTRY[model_id]
        return self.cache_root / spec.subdir / spec.filename

    def is_cached(self, model_id: str) -> bool:
        return self.path_for(model_id).exists()

    def ensure(self, model_id: str, progress_callback: ProgressCallback | None = None) -> Path:
        spec = REGISTRY[model_id]
        target = self.path_for(model_id)
        if target.exists():
            return target

        target.parent.mkdir(parents=True, exist_ok=True)
        self._download(spec.url, target, progress_callback)
        return target

    @staticmethod
    def _download(url: str, target: Path, progress_callback: ProgressCallback | None) -> None:
        tmp_path = target.with_suffix(target.suffix + ".part")
        with requests.get(url, stream=True, timeout=60) as response:
            response.raise_for_status()
            total = int(response.headers.get("content-length", 0))
            downloaded = 0
            with open(tmp_path, "wb") as f, tqdm(
                total=total, unit="B", unit_scale=True, desc=target.name
            ) as bar:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    f.write(chunk)
                    downloaded += len(chunk)
                    bar.update(len(chunk))
                    if progress_callback:
                        progress_callback(downloaded, total)
        tmp_path.rename(target)
