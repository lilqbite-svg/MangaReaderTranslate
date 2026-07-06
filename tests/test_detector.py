from pathlib import Path

from app.core.detector import ComicTextDetector
from app.models.manager import ModelManager

FIXTURE = Path(__file__).parent / "fixtures" / "sample_page.jpg"


def test_detects_at_least_one_region():
    if not FIXTURE.exists():
        import pytest

        pytest.skip("No fixture image at tests/fixtures/sample_page.jpg")

    import numpy as np
    from PIL import Image

    manager = ModelManager()
    detector = ComicTextDetector(manager.ensure("comic_text_detector"), device="cpu")
    image = np.array(Image.open(FIXTURE).convert("RGB"))
    regions = detector.detect(image)

    assert 1 <= len(regions) <= 60
    for region in regions:
        x1, y1, x2, y2 = region.bbox
        assert x2 > x1 and y2 > y1
        assert region.mask.shape == image.shape[:2]
