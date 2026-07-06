from __future__ import annotations

import re
import tempfile
import zipfile
from pathlib import Path

from app.io.strip_split import split_long_strip

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
ARCHIVE_EXTS = {".cbz", ".zip"}


def _natural_key(path: Path) -> list[int | str]:
    parts = re.split(r"(\d+)", path.name)
    return [int(p) if p.isdigit() else p.lower() for p in parts]


def _expand_long_strips(images: list[Path]) -> list[Path]:
    """Some raw/scanlation archives bundle a whole chapter as a handful of
    tall "long strip" images (several pages concatenated vertically) rather
    than one file per page - split those back into individual pages so the
    rest of the app (viewer, detector, OCR) sees normal single pages."""
    expanded: list[Path] = []
    for image in images:
        expanded.extend(split_long_strip(image))
    return expanded


def load_pages(path: Path) -> list[Path]:
    """Returns an ordered list of image file paths for a single image, a
    folder of images, or a CBZ/ZIP archive (extracted to a temp directory).
    Any unusually tall "long strip" image (several pages concatenated into
    one file) is transparently split into its individual pages."""
    path = Path(path)

    if path.is_file() and path.suffix.lower() in IMAGE_EXTS:
        return _expand_long_strips([path])

    if path.is_file() and path.suffix.lower() in ARCHIVE_EXTS:
        extract_dir = Path(tempfile.mkdtemp(prefix="mangareadertranslate_"))
        with zipfile.ZipFile(path) as zf:
            zf.extractall(extract_dir)
        images = [p for p in extract_dir.rglob("*") if p.suffix.lower() in IMAGE_EXTS]
        return _expand_long_strips(sorted(images, key=_natural_key))

    if path.is_dir():
        images = [p for p in path.iterdir() if p.suffix.lower() in IMAGE_EXTS]
        return _expand_long_strips(sorted(images, key=_natural_key))

    raise ValueError(f"Unsupported input: {path}")
