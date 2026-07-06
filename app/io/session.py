from __future__ import annotations

import pickle
from pathlib import Path

import cv2
import numpy as np

from app.core.types import PageResult, TextRegion
from app.models.manager import CACHE_ROOT

SESSION_PATH = CACHE_ROOT.parent / "session_autosave.pkl"

_FORMAT_VERSION = 1


def _encode_image(image: np.ndarray | None) -> bytes | None:
    if image is None:
        return None
    ok, buf = cv2.imencode(".png", cv2.cvtColor(image, cv2.COLOR_RGB2BGR))
    if not ok:
        raise RuntimeError("Failed to encode image for session autosave")
    return buf.tobytes()


def _decode_image(data: bytes | None) -> np.ndarray | None:
    if data is None:
        return None
    array = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_COLOR)
    return cv2.cvtColor(array, cv2.COLOR_BGR2RGB)


def save_session(image_paths: list[Path], results: dict[int, PageResult], src_lang: str, tgt_lang: str) -> None:
    """Best-effort autosave of in-progress work (translated pages + any manual
    text edits) so closing the app without exporting doesn't lose it. Skips
    each region's `mask` (a page-sized array per region, only needed during
    the original inpaint pass, not for redisplay/re-export/re-render) and
    stores images as PNG bytes rather than raw arrays to keep the file a
    reasonable size."""
    try:
        payload = {
            "version": _FORMAT_VERSION,
            "image_paths": [str(p) for p in image_paths],
            "src_lang": src_lang,
            "tgt_lang": tgt_lang,
            "results": {
                index: {
                    "source_path": result.source_path,
                    "cleaned_image": _encode_image(result.cleaned_image),
                    "output_image": _encode_image(result.output_image),
                    "regions": [
                        {
                            "bbox": r.bbox,
                            "is_bubble": r.is_bubble,
                            "angle": r.angle,
                            "style": r.style,
                            "source_text": r.source_text,
                            "translated_text": r.translated_text,
                            "confidence": r.confidence,
                        }
                        for r in result.regions
                    ],
                }
                for index, result in results.items()
            },
        }
        SESSION_PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = SESSION_PATH.with_suffix(".tmp")
        with open(tmp_path, "wb") as f:
            pickle.dump(payload, f, protocol=pickle.HIGHEST_PROTOCOL)
        tmp_path.replace(SESSION_PATH)
    except Exception:
        # Autosave is a convenience, not a critical path - a save failure
        # should never interrupt translation or crash the UI.
        pass


def has_saved_session() -> bool:
    return SESSION_PATH.exists()


def load_session() -> tuple[list[Path], dict[int, PageResult], str, str]:
    with open(SESSION_PATH, "rb") as f:
        payload = pickle.load(f)

    image_paths = [Path(p) for p in payload["image_paths"]]
    results: dict[int, PageResult] = {}
    for index, data in payload["results"].items():
        regions = [
            TextRegion(
                bbox=tuple(r["bbox"]),
                polygon=np.empty((0, 2), dtype=np.int32),
                mask=np.empty((0, 0), dtype=np.uint8),
                is_bubble=r["is_bubble"],
                angle=r["angle"],
                style=r["style"],
                source_text=r["source_text"],
                translated_text=r["translated_text"],
                confidence=r.get("confidence", 1.0),
            )
            for r in data["regions"]
        ]
        results[int(index)] = PageResult(
            source_path=data["source_path"],
            regions=regions,
            output_image=_decode_image(data["output_image"]),
            cleaned_image=_decode_image(data["cleaned_image"]),
        )
    return image_paths, results, payload["src_lang"], payload["tgt_lang"]


def clear_session() -> None:
    SESSION_PATH.unlink(missing_ok=True)
