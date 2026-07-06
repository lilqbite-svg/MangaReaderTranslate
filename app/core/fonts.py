from __future__ import annotations

from pathlib import Path

RESOURCES_FONTS = Path(__file__).resolve().parent.parent.parent / "resources" / "fonts"

# Comic lettering style roles, each mapped to a free/OFL-licensed font that
# plays the same visual role as the commercial fonts scanlation groups
# typically use (Anime Ace, Blambot's Eepsion/DeadMetro, Comicraft's CC
# fonts, etc.) - those are paid commercial fonts and aren't bundled here.
#
#   dialogue   - normal speech bubble text     (~Anime Ace / CC Astro City)
#   emphasis   - shouted/bold-italic dialogue  (~Anime Ace Bold Italic)
#   sfx        - free-floating sound effects   (~Eepsion/Manga Temple)
#   thought    - thought bubbles, handwritten   (~BetinaScriptC)
#   mechanical - phone/TV/robot "unnatural" voice (~Formalist/DeadMetroC)
_ROLE_CANDIDATES: dict[str, dict[str, list[Path]]] = {
    "latin": {
        "dialogue": [RESOURCES_FONTS / "ComicNeue-Regular.ttf", RESOURCES_FONTS / "NotoSans-Regular.ttf"],
        "emphasis": [RESOURCES_FONTS / "ComicNeue-BoldItalic.ttf", RESOURCES_FONTS / "ComicNeue-Bold.ttf"],
        "sfx": [RESOURCES_FONTS / "Bangers-Regular.ttf"],
        "thought": [RESOURCES_FONTS / "Caveat-Regular.ttf"],
        "mechanical": [RESOURCES_FONTS / "ShareTechMono-Regular.ttf"],
    },
    "cjk_ja": {
        "_default": [
            RESOURCES_FONTS / "NotoSansCJK-Regular.ttc",
            Path(r"C:\Windows\Fonts\meiryo.ttc"),
            Path(r"C:\Windows\Fonts\msgothic.ttc"),
        ],
    },
}

_FALLBACK = [RESOURCES_FONTS / "NotoSans-Regular.ttf", Path(r"C:\Windows\Fonts\arial.ttf")]


def font_path_for_role(script_group: str, style: str = "dialogue") -> Path:
    roles = _ROLE_CANDIDATES.get(script_group)
    if roles is None:
        candidates = _FALLBACK
    else:
        candidates = roles.get(style) or roles.get("_default") or roles.get("dialogue") or _FALLBACK

    for path in candidates:
        if path.exists():
            return path
    raise FileNotFoundError(f"No usable font found for script_group={script_group!r} style={style!r}. Tried: {candidates}")


def font_path_for_script(script_group: str) -> Path:
    """Back-compat helper: the plain "dialogue" role font for a script."""
    return font_path_for_role(script_group, "dialogue")
