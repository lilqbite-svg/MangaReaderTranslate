from __future__ import annotations

import tempfile
from pathlib import Path

import numpy as np
from PIL import Image

# Some raw/scanlation archives ship a chapter as one giant vertically-
# stacked "long strip" image (several pages concatenated with a small gap
# between them) instead of one file per page. Feeding that whole strip
# through the pipeline as a single "page" both looks wrong (the viewer has
# to shrink it down to a thin sliver to fit) and works badly (the detector/
# OCR are tuned for a normal single-page aspect ratio). This splits such a
# strip back into individual page images by finding the blank/uniform
# separator rows between them.

_ASPECT_THRESHOLD = 2.2  # height/width above this is unusually tall for one page
_MIN_GAP_HEIGHT = 18  # consecutive near-uniform rows required to count as a real seam,
# well above a normal in-page panel gutter (a handful of px) so a legitimate
# full-width panel border doesn't get mistaken for a page boundary
_MIN_SEGMENT_HEIGHT = 200  # ignore slivers this thin - almost certainly a misdetection
_UNIFORM_STD_THRESHOLD = 15.0  # per-row grayscale std dev below this counts as "flat" -
# real-world separator rows aren't always a pure flat color (compression
# noise, a subtle gradient/pattern strip) but sit far below actual page
# content, which is solidly 30+ once any line art or screentone is present


def _find_gap_runs(is_gap: np.ndarray) -> list[tuple[int, int]]:
    runs = []
    start = None
    for y, flat in enumerate(is_gap):
        if flat:
            if start is None:
                start = y
        elif start is not None:
            if y - start >= _MIN_GAP_HEIGHT:
                runs.append((start, y))
            start = None
    if start is not None and len(is_gap) - start >= _MIN_GAP_HEIGHT:
        runs.append((start, len(is_gap)))
    return runs


def split_long_strip(image_path: Path, output_dir: Path | None = None) -> list[Path]:
    """If `image_path` looks like several pages concatenated into one tall
    strip, splits it into separate page image files (written under
    `output_dir`, a fresh temp directory if not given) and returns them in
    reading order. Returns [image_path] unchanged if it doesn't look like a
    strip, or if no confident separators are found - this only ever adds
    pages, never silently mangles a normal single-page image."""
    with Image.open(image_path) as im:
        width, height = im.size
        if height / max(width, 1) < _ASPECT_THRESHOLD:
            return [image_path]
        gray = np.array(im.convert("L"))

    row_std = gray.std(axis=1)
    gap_runs = _find_gap_runs(row_std < _UNIFORM_STD_THRESHOLD)
    if not gap_runs:
        return [image_path]

    segments: list[tuple[int, int]] = []
    cursor = 0
    for gap_start, gap_end in gap_runs:
        if gap_start - cursor >= _MIN_SEGMENT_HEIGHT:
            segments.append((cursor, gap_start))
        cursor = gap_end
    if height - cursor >= _MIN_SEGMENT_HEIGHT:
        segments.append((cursor, height))

    if len(segments) <= 1:
        return [image_path]

    if output_dir is None:
        output_dir = Path(tempfile.mkdtemp(prefix="mangareadertranslate_split_"))
    output_dir.mkdir(parents=True, exist_ok=True)

    suffix = image_path.suffix if image_path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".bmp"} else ".png"
    results = []
    with Image.open(image_path) as full_image:
        full_image = full_image.convert("RGB")
        for i, (y1, y2) in enumerate(segments):
            crop = full_image.crop((0, y1, width, y2))
            out_path = output_dir / f"{image_path.stem}_p{i + 1:02d}{suffix}"
            crop.save(out_path)
            results.append(out_path)
    return results
