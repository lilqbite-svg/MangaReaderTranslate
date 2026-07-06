from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import onnxruntime as ort

from app.core.types import TextRegion

_INPUT_SIZE = 1024  # comic-text-detector's ONNX export uses a fixed 1024x1024 input
_MASK_THRESH = 0.3
_MIN_AREA = 60  # px^2, filters out noise specks in the binarized mask
_DILATE_FRACTION = 0.02  # kernel size as a fraction of the shorter image side
_SOLIDITY_EMPHASIS_THRESH = 0.7  # jagged/uneven text mask below this -> emphasis
_ANGLE_SFX_THRESH = 20.0  # degrees of tilt beyond which text is treated as SFX


def _estimate_angle_and_style(polygon: np.ndarray, area: float) -> tuple[float, str, bool]:
    """Best-effort heuristic from the TEXT PIXEL mask shape alone (we don't
    decode the detector's own bubble/class head, see module docstring), so
    this can't reliably tell a thought bubble from a shout bubble - it only
    distinguishes "tilted -> likely SFX" and "jagged/uneven strokes -> likely
    emphasis" from "the rest -> normal dialogue". Good enough to pick a
    plausibly-different font/orientation, not a guarantee of the true type.
    """
    rect = cv2.minAreaRect(polygon)
    (_, _), (rw, rh), angle = rect
    # Normalize so `angle` is the deviation from horizontal in (-45, 45].
    if rw < rh:
        angle += 90
    if angle > 45:
        angle -= 90
    elif angle <= -45:
        angle += 90

    hull = cv2.convexHull(polygon)
    hull_area = cv2.contourArea(hull)
    solidity = (area / hull_area) if hull_area > 0 else 1.0

    if abs(angle) > _ANGLE_SFX_THRESH:
        return angle, "sfx", False
    if solidity < _SOLIDITY_EMPHASIS_THRESH:
        return angle, "emphasis", True
    return angle, "dialogue", True


def _letterbox(image: np.ndarray, size: int = _INPUT_SIZE):
    h, w = image.shape[:2]
    scale = min(size / h, size / w)
    new_h, new_w = int(round(h * scale)), int(round(w * scale))
    resized = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
    pad_h, pad_w = size - new_h, size - new_w
    padded = cv2.copyMakeBorder(resized, 0, pad_h, 0, pad_w, cv2.BORDER_CONSTANT, value=(114, 114, 114))
    return padded, new_h, new_w


class ComicTextDetector:
    """Wraps the comic-text-detector ONNX model. Rather than decoding its
    YOLO-style detection head (whose exact anchor/stride config isn't public),
    this uses only its per-pixel text segmentation output: threshold it, take
    connected components, and derive a bbox/polygon/mask per component. This
    is a standard, robust way to turn a text-probability heatmap into regions
    without depending on undocumented detection-head decode parameters.
    """

    def __init__(self, onnx_path: Path, device: str = "auto") -> None:
        available = ort.get_available_providers()
        if device in ("auto", "cuda") and "CUDAExecutionProvider" in available:
            providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]
        else:
            providers = ["CPUExecutionProvider"]

        self._session = ort.InferenceSession(str(onnx_path), providers=providers)
        self.providers = self._session.get_providers()
        self._input_name = self._session.get_inputs()[0].name
        self._output_names = [o.name for o in self._session.get_outputs()]

    def detect(self, image_rgb: np.ndarray) -> list[TextRegion]:
        h, w = image_rgb.shape[:2]
        padded, new_h, new_w = _letterbox(image_rgb)
        padded_h, padded_w = padded.shape[:2]

        blob = padded.astype(np.float32) / 255.0
        blob = blob.transpose(2, 0, 1)[None, ...]

        outputs = self._session.run(self._output_names, {self._input_name: blob})
        mask = self._pick_mask_output(dict(zip(self._output_names, outputs)))

        # Crop off the letterbox padding (in mask-resolution units) then resize
        # up to the original image size.
        valid_h = round(mask.shape[0] * new_h / padded_h)
        valid_w = round(mask.shape[1] * new_w / padded_w)
        mask = mask[:valid_h, :valid_w]
        mask_full = cv2.resize(mask, (w, h), interpolation=cv2.INTER_LINEAR)

        binary = (mask_full > _MASK_THRESH).astype(np.uint8) * 255

        # The raw mask lights up per-character, leaving individual kanji/kana
        # as isolated blobs. Dilate before connected-components so characters
        # that belong to the same text line/bubble merge into one region
        # (bubbles are far enough apart that this doesn't merge across them).
        dilate_size = max(3, int(min(h, w) * _DILATE_FRACTION))
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (dilate_size, dilate_size))
        dilated = cv2.dilate(binary, kernel, iterations=1)
        num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(dilated, connectivity=8)

        regions: list[TextRegion] = []
        for label in range(1, num_labels):
            x, y, bw, bh, area = stats[label]
            if area < _MIN_AREA:
                continue
            region_mask = np.zeros((h, w), dtype=np.uint8)
            region_mask[(labels == label) & (binary > 0)] = 255
            contours, _ = cv2.findContours(region_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            polygon = (
                contours[0].reshape(-1, 2)
                if contours
                else np.array([[x, y], [x + bw, y], [x + bw, y + bh], [x, y + bh]])
            )
            angle, style, is_bubble = _estimate_angle_and_style(polygon, float(area))
            regions.append(
                TextRegion(
                    bbox=(int(x), int(y), int(x + bw), int(y + bh)),
                    polygon=polygon,
                    mask=region_mask,
                    is_bubble=is_bubble,
                    angle=angle,
                    style=style,
                )
            )
        return regions

    @staticmethod
    def _pick_mask_output(outputs: dict[str, np.ndarray]) -> np.ndarray:
        """The comic-text-detector ONNX export exposes a "seg" output: a
        single-channel (1, 1, H, W) full-resolution text-probability map.
        ("blk" is a raw YOLO-style detection head we deliberately don't
        decode - its anchor/stride config isn't public - and "det" is an
        auxiliary (1, 2, H, W) map we don't need.) Falls back to picking
        whichever 4D output has the largest spatial area if "seg" is absent,
        in case a future model export renames it.
        """
        if "seg" in outputs:
            best = np.asarray(outputs["seg"])[0, 0]
        else:
            best = None
            best_area = -1
            for arr in outputs.values():
                arr = np.asarray(arr)
                if arr.ndim == 4:
                    candidate = arr[0, 0]
                elif arr.ndim == 3:
                    candidate = arr[0]
                else:
                    continue
                area = candidate.shape[0] * candidate.shape[1]
                if area > best_area:
                    best_area = area
                    best = candidate
            if best is None:
                raise RuntimeError("comic-text-detector: could not find a spatial mask output among model outputs")

        if best.max() > 1.0 or best.min() < 0.0:
            best = 1 / (1 + np.exp(-best))  # sigmoid, in case these are raw logits
        return best.astype(np.float32)
