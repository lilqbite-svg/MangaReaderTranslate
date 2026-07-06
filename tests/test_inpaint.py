import numpy as np

from app.core.inpaint import LamaInpainter
from app.models.manager import ModelManager


def test_masked_text_pixels_are_removed():
    manager = ModelManager()
    inpainter = LamaInpainter(manager.ensure("lama_manga"), device="cpu")

    image = np.full((256, 256, 3), 255, dtype=np.uint8)
    mask = np.zeros((256, 256), dtype=np.uint8)
    # A black square standing in for text, inside the masked region.
    image[100:150, 100:150] = 0
    mask[90:160, 90:160] = 255

    result = inpainter.clean(image, mask)

    region = result[100:150, 100:150]
    assert region.mean() > 100  # no longer dominated by black "text" pixels
    outside = result[:50, :50]
    assert np.array_equal(outside, image[:50, :50])  # untouched outside the mask
