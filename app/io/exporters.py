from __future__ import annotations

import io
import zipfile
from pathlib import Path

from PIL import Image

from app.core.types import PageResult


def save_images(results: list[PageResult], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    for i, result in enumerate(results):
        if result.output_image is None:
            continue
        out_path = out_dir / f"{i:03d}_{Path(result.source_path).stem}.png"
        Image.fromarray(result.output_image).save(out_path)


def save_cbz(results: list[PageResult], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for i, result in enumerate(results):
            if result.output_image is None:
                continue
            buf = io.BytesIO()
            Image.fromarray(result.output_image).save(buf, format="PNG")
            zf.writestr(f"{i:03d}_{Path(result.source_path).stem}.png", buf.getvalue())
