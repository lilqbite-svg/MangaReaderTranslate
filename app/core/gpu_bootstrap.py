from __future__ import annotations

import os
import sys
from pathlib import Path


def register_nvidia_dll_dirs() -> None:
    """pip-installed `nvidia-*-cuXX` packages ship their CUDA runtime DLLs
    (cublas, cudnn, cufft, curand, nvrtc, ...) inside the venv's
    site-packages/nvidia/<component>/bin, but unlike PyTorch, onnxruntime and
    ctranslate2 don't know to look there - Windows only searches the process
    PATH and a few default locations for DLL dependencies. This adds every
    such bin/ directory to the DLL search path, plus the system-wide CUDA
    Toolkit's bin dir if one is installed (newer cublas/cudart builds with
    Blackwell/sm_120 kernel support aren't all available as pip wheels yet),
    so `onnxruntime`'s CUDAExecutionProvider and `ctranslate2`'s cuda device
    can actually find the libraries they need. Must run before
    onnxruntime/ctranslate2 create any GPU session. No-op on non-Windows or
    if nothing GPU-related is installed (falls back to CPU as usual).
    """
    if sys.platform != "win32":
        return

    dirs: list[Path] = []

    # Dev venv layout: .venv/Lib/site-packages/nvidia/<component>/bin. In a
    # PyInstaller-frozen build there's no venv at all - sys.prefix points
    # somewhere inside the bundle with a completely different layout, so that
    # path never matches and this whole function was silently a no-op when
    # frozen. collect_all("nvidia"-owning packages) instead bundles each
    # package's files under sys._MEIPASS, preserving its internal folder
    # structure (nvidia/<component>/bin/*.dll), so check there too.
    candidate_roots = [Path(sys.prefix) / "Lib" / "site-packages" / "nvidia"]
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidate_roots.append(Path(meipass) / "nvidia")

    for nvidia_root in candidate_roots:
        if not nvidia_root.is_dir():
            continue
        for component_dir in nvidia_root.iterdir():
            bin_dir = component_dir / "bin"
            if bin_dir.is_dir():
                dirs.append(bin_dir)

    cuda_path = os.environ.get("CUDA_PATH")
    if cuda_path:
        toolkit_bin = Path(cuda_path) / "bin" / "x64"
        if toolkit_bin.is_dir():
            dirs.append(toolkit_bin)

    for d in dirs:
        # LOAD_LIBRARY_SEARCH_USER_DIRS-based lookup - covers LoadLibraryEx
        # calls that opt into it (e.g. onnxruntime's own provider loading).
        os.add_dll_directory(str(d))

    # cuDNN loads its own computational-backend sub-DLLs (cudnn_graph64_9.dll
    # etc.) internally via plain LoadLibrary with no search flags, which only
    # honors PATH, not AddDllDirectory - so the same directories need to be on
    # PATH too or that lazy load fails even though add_dll_directory succeeded.
    os.environ["PATH"] = os.pathsep.join([*(str(d) for d in dirs), os.environ.get("PATH", "")])
