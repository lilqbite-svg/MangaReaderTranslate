from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


@dataclass(frozen=True)
class Language:
    ui_code: str
    display_name: str
    nllb_code: str
    script_group: str


@dataclass
class TextRegion:
    """A single detected text/bubble region on a page."""

    bbox: tuple[int, int, int, int]  # x1, y1, x2, y2 in page pixel coords
    polygon: np.ndarray  # Nx2 int array of the region outline
    mask: np.ndarray  # HxW uint8 mask (255 inside region), same size as page image
    is_bubble: bool = True  # False for free-floating text (SFX)
    angle: float = 0.0  # estimated rotation of the original text, degrees
    style: str = "dialogue"  # dialogue | emphasis | sfx | thought | mechanical
    source_text: str = ""
    translated_text: str = ""
    confidence: float = 1.0  # OCR confidence 0-1; 1.0 where the backend doesn't report one (manga-ocr)
    custom_font_path: str = ""  # non-empty overrides the script/style-based font pick, just for this box


@dataclass
class PageResult:
    source_path: str
    regions: list[TextRegion] = field(default_factory=list)
    output_image: np.ndarray | None = None
    cleaned_image: np.ndarray | None = None  # inpainted background, before any text is drawn
