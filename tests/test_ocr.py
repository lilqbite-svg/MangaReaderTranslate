from pathlib import Path

FIXTURE = Path(__file__).parent / "fixtures" / "sample_crop.png"


def test_manga_ocr_returns_nonempty_text():
    if not FIXTURE.exists():
        import pytest

        pytest.skip("No fixture crop at tests/fixtures/sample_crop.png")

    import numpy as np
    from PIL import Image

    from app.core.ocr_manga import MangaOcr

    ocr = MangaOcr()
    crop = np.array(Image.open(FIXTURE).convert("RGB"))
    text = ocr.recognize(crop)

    assert isinstance(text, str)
    assert len(text.strip()) > 0
