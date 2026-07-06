from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from app.core.gpu_bootstrap import register_nvidia_dll_dirs

register_nvidia_dll_dirs()

from app.core.detector import ComicTextDetector
from app.core.inpaint import LamaInpainter
from app.core.langdetect import detect_source_language
from app.core.langs import get as get_lang
from app.core.ocr import OcrEngine
from app.core.renderer import draw_translated_text
from app.core.translator import NLLBTranslator
from app.core.types import PageResult
from app.models.manager import CACHE_ROOT, ModelManager

NLLB_CT2_DIR = CACHE_ROOT / "translate" / "nllb-200-distilled-600M-ct2"


class Pipeline:
    """Orchestrates detect -> OCR -> translate -> inpaint -> render for a
    single page. This is the one seam the CLI, tests, and (later) the Qt UI
    all call into."""

    def __init__(self, device: str = "auto", ocr_backend_overrides: dict[str, str] | None = None) -> None:
        if not NLLB_CT2_DIR.exists():
            import os
            import sys

            parent = NLLB_CT2_DIR.parent
            local_appdata = os.environ.get("LOCALAPPDATA", "")
            try:
                appdata_listing = os.listdir(local_appdata) if local_appdata else "N/A"
            except Exception as list_exc:
                appdata_listing = f"<listdir failed: {list_exc!r}>"
            debug = (
                f"NLLB_CT2_DIR={NLLB_CT2_DIR!r} pathlib.exists={NLLB_CT2_DIR.exists()} "
                f"os.path.exists={os.path.exists(str(NLLB_CT2_DIR))}\n"
                f"CACHE_ROOT={CACHE_ROOT!r} exists={CACHE_ROOT.exists()}\n"
                f"parent={parent!r} exists={parent.exists()} "
                f"contents={list(parent.iterdir()) if parent.exists() else 'N/A'}\n"
                f"LOCALAPPDATA={local_appdata!r}\n"
                f"listdir(LOCALAPPDATA) has 'MangaReaderTranslate'? "
                f"{'MangaReaderTranslate' in appdata_listing if isinstance(appdata_listing, list) else appdata_listing}\n"
                f"full listdir(LOCALAPPDATA)={appdata_listing}\n"
                f"sys.frozen={getattr(sys, 'frozen', False)} sys.prefix={sys.prefix!r} "
                f"sys.executable={sys.executable!r}"
            )
            raise RuntimeError(
                f"NLLB CTranslate2 model not found at {NLLB_CT2_DIR}. "
                "Run `python scripts/convert_nllb_to_ct2.py` first.\n\n" + debug
            )

        manager = ModelManager()
        detector_path = manager.ensure("comic_text_detector")
        lama_path = manager.ensure("lama_manga")

        self.detector = ComicTextDetector(detector_path, device=device)
        self.ocr = OcrEngine(backend_overrides=ocr_backend_overrides)
        self.translator = NLLBTranslator(NLLB_CT2_DIR, device=device)
        # Forced to CPU regardless of the device setting: text is always
        # rendered in black, so a GPU inference glitch that silently returns
        # garbage/near-zero pixels here (no exception - the ONNX session call
        # still "succeeds") produces black text on a black background, i.e.
        # an apparently blank page - not a crash, so none of this project's
        # earlier GPU/DLL fixes would have caught it. LaMa here is a small
        # model on a page-sized image, so CPU is still fast enough that this
        # isn't a meaningful performance regression.
        self.inpainter = LamaInpainter(lama_path, device="cpu")

    def process_page(
        self, image_path: Path, src_lang: str, tgt_lang: str, font_override: str = ""
    ) -> PageResult:
        tgt = get_lang(tgt_lang)

        image = np.array(Image.open(image_path).convert("RGB"))
        regions = self.detector.detect(image)

        if src_lang == "auto":
            src_lang = detect_source_language(image, regions)
        src = get_lang(src_lang)

        for region in regions:
            x1, y1, x2, y2 = region.bbox
            crop = image[y1:y2, x1:x2]
            region.source_text, region.confidence = self.ocr.recognize(crop, src_lang)

        # Skip empty/whitespace-only OCR reads entirely rather than handing
        # them to NLLB: an empty source string isn't "nothing to translate"
        # to the model, it hallucinates a plausible-looking short phrase
        # (observed: translating "" to Russian consistently produced
        # "Оригинальная"), which would then get rendered as bogus text over
        # regions that never had any real content (decorative marks, logos).
        translatable = [(i, r.source_text) for i, r in enumerate(regions) if r.source_text.strip()]
        translations = (
            self.translator.translate([t for _, t in translatable], src.nllb_code, tgt.nllb_code)
            if translatable
            else []
        )
        for (i, _), translation in zip(translatable, translations):
            regions[i].translated_text = translation

        # Only erase regions we're actually about to replace with translated
        # text. A region with no translation (OCR came back empty - RapidOCR
        # rejected it as low-confidence, or the source script isn't wired up
        # for that region's script_group) would otherwise get wiped by LaMa
        # and then have nothing rendered back into it, leaving a blank hole
        # where legible original text used to be - worse than leaving the
        # source text untouched.
        inpaintable = [r for r in regions if r.translated_text.strip()]
        if inpaintable:
            combined_mask = np.zeros(image.shape[:2], dtype=np.uint8)
            for region in inpaintable:
                combined_mask = np.maximum(combined_mask, region.mask)
            # The detector's mask hugs the text pixels tightly, so LaMa can
            # leave faint strokes of the original glyphs right at the mask's
            # edge (observed as the old text showing through under the new
            # translation). Grow the mask a few pixels first so it clears
            # with a small margin instead of following the glyph outlines
            # exactly.
            dilate_px = max(3, round(min(image.shape[:2]) * 0.004))
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (dilate_px * 2 + 1, dilate_px * 2 + 1))
            combined_mask = cv2.dilate(combined_mask, kernel, iterations=1)
            cleaned = self.inpainter.clean(image, combined_mask)
        else:
            cleaned = image

        output = rerender_page(cleaned, regions, tgt.script_group, default_font_override=font_override)

        return PageResult(source_path=str(image_path), regions=regions, output_image=output, cleaned_image=cleaned)


def rerender_page(
    cleaned_image: np.ndarray, regions: list, tgt_script_group: str, default_font_override: str = ""
) -> np.ndarray:
    """Redraws every region's current `translated_text` onto the already
    -inpainted background. Used both by process_page and by the UI's manual
    correction panel: editing one region's text and calling this again only
    re-runs cheap Pillow rendering, not detection/OCR/translation/inpainting.
    Font precedence per region: the region's own custom_font_path, else
    `default_font_override` (a page- or app-wide custom font), else the
    normal automatic script/style pick."""
    output = cleaned_image.copy()
    for region in regions:
        output = draw_translated_text(
            output,
            region.bbox,
            region.translated_text,
            tgt_script_group,
            style=region.style,
            angle=region.angle,
            font_override=region.custom_font_path or default_font_override,
        )
    return output
