# MangaReaderTranslate

A free, fully local/offline manga translator. No cloud APIs, no accounts. Detects
text in manga page images, translates it, and renders the translation back into
the page.

**Status: all 4 phases done.** Desktop app (PySide6), ~40 source/target
languages, manual text correction, GPU acceleration, standalone `.exe` packaging.

## How it works

1. **Detection** — [comic-text-detector](https://github.com/dmMaze/comic-text-detector)
   (ONNX) finds text/bubble regions and estimates each region's rotation angle
   and style (dialogue/emphasis/SFX) from the text mask shape.
2. **OCR** — [manga-ocr](https://github.com/kha-white/manga-ocr) reads Japanese;
   [RapidOCR](https://github.com/RapidAI/RapidOCR) (PP-OCRv5, pure ONNX, no
   PaddlePaddle) handles the other ~39 languages, routed by script.
3. **Translation** — [NLLB-200-distilled-600M](https://huggingface.co/facebook/nllb-200-distilled-600M),
   converted to [CTranslate2](https://github.com/OpenNMT/CTranslate2) for fast
   local inference across all language pairs.
4. **Inpainting** — a LaMa-based model
   ([ogkalu/lama-manga-onnx-dynamic](https://huggingface.co/ogkalu/lama-manga-onnx-dynamic))
   removes the original text, preserving art/screentone.
5. **Rendering** — the translated text is word-wrapped, auto-sized, rotated to
   match the original's angle, and drawn back into each region with Pillow +
   free (OFL) fonts chosen by style role (dialogue/emphasis/SFX/thought/
   mechanical — see Licensing notes below for why these aren't the commercial
   scanlation fonts like Anime Ace).

All models run locally via `onnxruntime` / `ctranslate2`, with CUDA GPU
acceleration (falls back to CPU automatically if no compatible GPU/CUDA setup
is found — see the GPU section below for what's actually required).

## Setup

Requires **Python 3.11** specifically (newer versions aren't yet supported by
the ML dependencies below).

```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Detector and inpainting models download automatically on first run to
`%LOCALAPPDATA%\MangaReaderTranslate\models\`. manga-ocr and RapidOCR download
their own weights on first use per language.

NLLB needs one extra manual step: `scripts/convert_nllb_to_ct2.py` converts a
local snapshot of `facebook/nllb-200-distilled-600M` rather than downloading it
itself, because `huggingface_hub`'s downloader proved unreliable on flaky
connections for a ~2.4GB file. Fetch the files first (resumable, so a dropped
connection just re-run the same command):

```
mkdir "%LOCALAPPDATA%\MangaReaderTranslate\models\translate\nllb-200-distilled-600M-hf"
cd "%LOCALAPPDATA%\MangaReaderTranslate\models\translate\nllb-200-distilled-600M-hf"
for %f in (config.json generation_config.json pytorch_model.bin sentencepiece.bpe.model special_tokens_map.json tokenizer.json tokenizer_config.json) do curl -L --retry 15 --retry-delay 3 --retry-all-errors -C - -o %f "https://huggingface.co/facebook/nllb-200-distilled-600M/resolve/main/%f"
```

Then convert to CTranslate2 (one-time, ~1 minute, purely local/CPU):

```
python scripts\convert_nllb_to_ct2.py
```

Note: `manga-ocr` doesn't pin its `transformers` version, and the newest
`transformers` releases dropped support for its legacy `BertJapaneseTokenizer`
(fails with `Couldn't instantiate the backend tokenizer...`). `requirements.txt`
pins `transformers<5,>=4.40` to avoid this — don't upgrade past 5 without
verifying manga-ocr still loads.

## GPU acceleration

Works, but on very new GPUs (Blackwell / RTX 50-series) it needs more than
`pip install onnxruntime-gpu`:

1. `requirements.txt` already pins `onnxruntime-gpu==1.27.0` and the
   `nvidia-*-cu12` pip packages (cublas/cudnn/cufft/curand/nvrtc) — these
   provide cuDNN 9 and are enough on their own for older GPUs.
2. **On a Blackwell GPU specifically**, `onnxruntime-gpu` needs CUDA **13.x**
   runtime libraries (`cublas64_13.dll` etc.) that aren't available as clean
   pip wheels yet (`nvidia-cublas-cu13` on PyPI is just a placeholder). Install
   the official [CUDA 13.x Toolkit](https://developer.nvidia.com/cuda-downloads)
   for Windows (large, ~2.5GB, needs admin rights) — this also fixes
   `ctranslate2`'s GPU support, since it shares the same cuDNN dependency.
3. **Reboot after installing the Toolkit.** The driver/toolkit's kernel-mode
   components didn't get picked up without one on the machine this was
   developed on — GPU init failed with `WinError 1114 (DLL init failed)` until
   a reboot.
4. `app/core/gpu_bootstrap.py` handles the rest automatically: it registers
   both the pip `nvidia-*-cu12` package directories and the system CUDA
   Toolkit's `bin\x64` directory (via `CUDA_PATH`) as DLL search
   directories — **and** prepends them to `PATH`. Both are necessary: cuDNN
   loads its own computational-backend sub-DLLs (e.g. `cudnn_graph64_9.dll`)
   internally via plain `LoadLibrary` with no search flags, which only honors
   `PATH`, not the `os.add_dll_directory()` mechanism `onnxruntime` itself
   uses for its own provider DLL.
5. Verify with the device selector in the app's Settings dialog (or
   `--device auto`/`cuda` on the CLI) — if GPU init fails for any reason it
   silently falls back to CPU rather than crashing, so check
   `Pipeline.detector.providers` / `Pipeline.translator.device` if you want to
   confirm which one is actually active.

## Usage

CLI (single page):
```
python -m app.core_cli path\to\page.jpg --src ja --tgt en --out out.png
```

Desktop app:
```
python -m app.main
```
Open a single image, a folder, or a CBZ/ZIP archive; pick source/target
language (or "Auto-detect"); "Translate All" runs in the background with a
progress bar; edit any box's translation and hit "Re-render this box" to fix
it without re-running OCR/translation/inpainting; export as images or a CBZ.

## Packaging as a standalone .exe

```
pip install pyinstaller
pyinstaller pyinstaller.spec
```
Produces `dist/MangaReaderTranslate/MangaReaderTranslate.exe` (~2.3GB folder,
mostly torch/onnxruntime-gpu/ctranslate2/PySide6 binaries) that runs without a
separate Python install. Models still download to `%LOCALAPPDATA%` on first
use, same as running from source.

## License

This project's own code is **MIT-licensed** (see [LICENSE](LICENSE)). It
depends at runtime on several third-party models with their own, different
licenses — see below, since one of them (NLLB) restricts the *whole running
app* to non-commercial use regardless of this project's own MIT license.

## Licensing notes

- **NLLB-200** checkpoints are released by Meta under **CC-BY-NC-4.0 —
  non-commercial use only**. This tool is free/personal-use, which is fine,
  but it cannot be sold or bundled into a commercial product without swapping
  the translation backend.
- `comic-text-detector` is **GPL-3.0**. This project only calls its published
  ONNX weights over `onnxruntime` (no GPL source code is vendored), but if you
  plan to redistribute this app, check GPL-3.0 compatibility for your use case.
- LaMa/`lama-manga-onnx-dynamic`, RapidOCR, and Noto Sans are **Apache-2.0** /
  **SIL OFL** — no restrictions beyond attribution.
- The bundled fonts (Comic Neue, Bangers, Caveat, Share Tech Mono, all **SIL
  OFL**) are deliberately *not* the commercial scanlation-standard fonts
  (Anime Ace, Blambot's Eepsion/DeadMetro, Comicraft's CC fonts, etc.) — those
  are paid fonts most scanlation groups use without a license. This project
  maps the same lettering *roles* (dialogue/emphasis/SFX/thought/mechanical)
  onto free equivalents instead.

## Known limitations

- Auto-detect source language is a Unicode-range heuristic over a RapidOCR
  first-pass read, not a real language-ID model — reliable for ja/ko/zh/ru/
  el/ar/hi/th, defaults to English otherwise. Always overridable in the UI.
- No RapidOCR recognition model wired up yet for Hebrew, Bengali, or Khmer.
- Region style/rotation detection is a shape heuristic on the text-pixel mask
  (solidity + angle), not a trained classifier — it can't reliably tell a
  thought bubble from a shout bubble, only "tilted -> probably SFX" and
  "jagged strokes -> probably emphasis".
