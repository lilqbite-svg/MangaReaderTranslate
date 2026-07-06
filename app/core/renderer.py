from __future__ import annotations

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from app.core.fonts import font_path_for_role

_MIN_FONT_SIZE = 10
_MAX_FONT_SIZE = 72
_PADDING_RATIO = 0.12  # inset from the bubble bbox so text doesn't touch the border


def _wrap_to_width(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    words = text.split()
    if not words:
        return [""]

    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        candidate = f"{current} {word}"
        if draw.textlength(candidate, font=font) <= max_width:
            current = candidate
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def _line_height(font: ImageFont.FreeTypeFont) -> int:
    # font.getmetrics() gives the font's own design ascent/descent, which
    # covers whatever script is actually being rendered (Cyrillic descenders
    # like "р"/"у"/"ф", Latin "g"/"y", etc). A fixed probe string like "Ag"
    # only reflects Latin metrics and under-measures other scripts, which was
    # letting later lines drift past the bottom of the box and get clipped.
    ascent, descent = font.getmetrics()
    return ascent + descent


def _fit_text(
    draw: ImageDraw.ImageDraw, text: str, font_path, box_w: int, box_h: int
) -> tuple[ImageFont.FreeTypeFont, list[str], float, float]:
    # Shrink-to-fit within the region's own box keeps size proportional to the
    # original bubble (bigger bubble -> bigger text) rather than a fixed size,
    # so the rendered translation doesn't wildly over/under-scale relative to
    # what was there before.
    for size in range(_MAX_FONT_SIZE, _MIN_FONT_SIZE - 1, -1):
        font = ImageFont.truetype(str(font_path), size)
        lines = _wrap_to_width(draw, text, font, box_w)
        total_height = _line_height(font) * len(lines) * 1.15
        widest = max(draw.textlength(line, font=font) for line in lines)
        if total_height <= box_h and widest <= box_w:
            return font, lines, total_height, widest
    # Even the smallest size doesn't fit (unusually long translation in a
    # small bubble, or - notably - a single unbreakable "word" like a
    # hyphenated name that _wrap_to_width can never split across lines) -
    # return it anyway with its real width/height so the caller can grow the
    # canvas instead of silently clipping lines off.
    font = ImageFont.truetype(str(font_path), _MIN_FONT_SIZE)
    lines = _wrap_to_width(draw, text, font, box_w)
    total_height = _line_height(font) * len(lines) * 1.15
    widest = max(draw.textlength(line, font=font) for line in lines)
    return font, lines, total_height, widest


def draw_translated_text(
    image_rgb: np.ndarray,
    bbox: tuple[int, int, int, int],
    text: str,
    script_group: str,
    style: str = "dialogue",
    angle: float = 0.0,
    font_override: str = "",
) -> np.ndarray:
    """Draws `text`, word-wrapped and auto-shrunk to fit, centered inside `bbox`
    (x1, y1, x2, y2) on a copy of `image_rgb`. `style` selects the font role
    (dialogue/emphasis/sfx/thought/mechanical, see app/core/fonts.py) and
    `angle` rotates the rendered text to match the original's tilt (degrees,
    0 = horizontal) so it keeps the same orientation as the source.
    `font_override`, if non-empty, is a path to a user-chosen font file that
    replaces the automatic script/style-based pick entirely."""
    if not text.strip():
        return image_rgb

    x1, y1, x2, y2 = bbox
    box_w, box_h = x2 - x1, y2 - y1
    pad_x, pad_y = int(box_w * _PADDING_RATIO), int(box_h * _PADDING_RATIO)
    inner_w, inner_h = max(1, box_w - 2 * pad_x), max(1, box_h - 2 * pad_y)

    font_path = font_override or font_path_for_role(script_group, style)

    # Measure first on a scratch context (textlength/getbbox don't depend on
    # canvas size), then size the real layer to whatever the text actually
    # needs. If a translation is too long to fit even at _MIN_FONT_SIZE, grow
    # the layer past the bubble's own box (taller AND/OR wider) rather than
    # clipping - a single unbreakable "word" (e.g. a hyphenated name, or just
    # a long word in a narrow tag-shaped box) can be wider than the box at
    # any size, since _wrap_to_width only ever breaks on whitespace. Without
    # widening too, a too-wide line got centered and silently clipped
    # symmetrically at both edges (e.g. "Яма-сан!" rendering as "MA-CAH"). A
    # bit of overflow into the surrounding art still reads fine, a silently
    # clipped word doesn't.
    measure_draw = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    font, lines, total_height, widest = _fit_text(measure_draw, text, font_path, inner_w, inner_h)

    layer_w = max(inner_w, int(widest) + 2)
    layer_h = max(inner_h, int(total_height) + 2)
    layer = Image.new("RGBA", (layer_w, layer_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)

    line_height = _line_height(font)
    start_y = (layer_h - total_height) / 2

    for i, line in enumerate(lines):
        line_width = draw.textlength(line, font=font)
        line_x = (layer_w - line_width) / 2
        line_y = start_y + i * line_height * 1.15
        draw.text((line_x, line_y), line, font=font, fill=(0, 0, 0, 255))

    if abs(angle) > 0.5:
        layer = layer.rotate(angle, expand=True, resample=Image.BICUBIC)

    pil_image = Image.fromarray(image_rgb).convert("RGB")
    cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
    paste_x, paste_y = cx - layer.width // 2, cy - layer.height // 2
    pil_image.paste(layer, (paste_x, paste_y), layer)

    return np.array(pil_image)
