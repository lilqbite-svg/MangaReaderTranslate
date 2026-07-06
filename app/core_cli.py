"""Phase 1 CLI entry point.

    python -m app.core_cli path/to/page.jpg --src ja --tgt en --out out.png
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PIL import Image

from app.core.pipeline import Pipeline

# Windows consoles often default to a legacy codepage (e.g. cp1251) that can't
# encode Japanese/CJK text; force UTF-8 with a safe fallback so printing OCR'd
# source text never crashes the run after the (expensive) pipeline succeeded.
sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def main() -> None:
    parser = argparse.ArgumentParser(description="Translate a single manga page image.")
    parser.add_argument("image", type=Path)
    parser.add_argument("--src", required=True, help="Source language code, e.g. ja")
    parser.add_argument("--tgt", required=True, help="Target language code, e.g. en")
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--device", default="auto", choices=["auto", "cuda", "cpu"])
    args = parser.parse_args()

    out_path = args.out or args.image.with_name(f"{args.image.stem}_translated{args.image.suffix}")

    pipeline = Pipeline(device=args.device, status_callback=print)
    result = pipeline.process_page(args.image, args.src, args.tgt)

    Image.fromarray(result.output_image).save(out_path)

    for i, region in enumerate(result.regions):
        print(f"[{i}] {region.source_text!r} -> {region.translated_text!r}")
    print(f"Saved: {out_path}")


if __name__ == "__main__":
    main()
