from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import onnxruntime as ort


def _pad_to_multiple(image: np.ndarray, multiple: int = 8) -> tuple[np.ndarray, int, int]:
    h, w = image.shape[:2]
    new_h = ((h + multiple - 1) // multiple) * multiple
    new_w = ((w + multiple - 1) // multiple) * multiple
    pad_h, pad_w = new_h - h, new_w - w
    if image.ndim == 3:
        padded = np.pad(image, ((0, pad_h), (0, pad_w), (0, 0)), mode="reflect" if pad_h or pad_w else "constant")
    else:
        padded = np.pad(image, ((0, pad_h), (0, pad_w)), mode="reflect" if pad_h or pad_w else "constant")
    return padded, h, w


class LamaInpainter:
    """Runs a LaMa (big-lama derived) ONNX model to remove text from masked
    regions of a page image, preserving surrounding art/screentone texture.
    Model: ogkalu/lama-manga-onnx-dynamic (Apache-2.0), a LaMa variant tuned
    for manga/anime line-art + screentone backgrounds.
    """

    def __init__(self, onnx_path: Path, device: str = "auto") -> None:
        providers = self._resolve_providers(device)
        self._session = ort.InferenceSession(str(onnx_path), providers=providers)
        self.providers = self._session.get_providers()

        inputs = self._session.get_inputs()
        if len(inputs) != 2:
            raise RuntimeError(
                f"Expected LaMa ONNX model to have 2 inputs (image, mask), got {len(inputs)}: "
                f"{[i.name for i in inputs]}"
            )
        # Identify which input is the 3-channel image vs the 1-channel mask by
        # inspecting declared shapes; falls back to declaration order if shapes
        # are fully dynamic.
        self._image_input, self._mask_input = inputs[0].name, inputs[1].name
        for inp in inputs:
            shape = inp.shape
            channel_dim = shape[1] if len(shape) == 4 else None
            if channel_dim == 1:
                self._mask_input = inp.name
            elif channel_dim == 3:
                self._image_input = inp.name
        self._output_name = self._session.get_outputs()[0].name

    @staticmethod
    def _resolve_providers(device: str) -> list[str]:
        available = ort.get_available_providers()
        if device in ("auto", "cuda") and "CUDAExecutionProvider" in available:
            return ["CUDAExecutionProvider", "CPUExecutionProvider"]
        return ["CPUExecutionProvider"]

    def clean(self, image_rgb: np.ndarray, mask: np.ndarray) -> np.ndarray:
        """image_rgb: HxWx3 uint8. mask: HxW uint8, 255 where text should be
        removed. Returns an HxWx3 uint8 image with masked regions inpainted."""
        padded_img, orig_h, orig_w = _pad_to_multiple(image_rgb)
        padded_mask, _, _ = _pad_to_multiple(mask)

        img_in = padded_img.astype(np.float32) / 255.0
        img_in = img_in.transpose(2, 0, 1)[None, ...]  # 1x3xHxW

        mask_in = (padded_mask.astype(np.float32) / 255.0)
        mask_in = (mask_in > 0.5).astype(np.float32)[None, None, ...]  # 1x1xHxW

        result = self._session.run(
            [self._output_name],
            {self._image_input: img_in, self._mask_input: mask_in},
        )[0]

        out = result[0]  # 3xHxW
        out = np.clip(out, 0, 1) if out.max() <= 1.5 else np.clip(out, 0, 255) / 255.0
        out = (out.transpose(1, 2, 0) * 255.0).astype(np.uint8)
        out = out[:orig_h, :orig_w]

        # Only replace pixels inside the mask; keep original elsewhere so any
        # border padding artifacts never leak into untouched art.
        mask_bool = (mask > 127)[..., None]
        return np.where(mask_bool, out, image_rgb)
