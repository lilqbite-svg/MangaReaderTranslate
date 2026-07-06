"""Pre-downloads and converts facebook/nllb-200-distilled-600M (HF/PyTorch)
to CTranslate2 int8 ahead of time.

The app now does this automatically on first translation (see
app/models/nllb_setup.py), so running this script by hand is optional - it's
here for downloading the ~2.4GB model during off-hours, or from a plain CLI
without launching the desktop app:

    python scripts/convert_nllb_to_ct2.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.models.nllb_setup import ensure_nllb_ct2


def main() -> None:
    result_dir = ensure_nllb_ct2(status_callback=print)
    print(f"Ready: {result_dir}")


if __name__ == "__main__":
    main()
