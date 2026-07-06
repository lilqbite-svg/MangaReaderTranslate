# Build with: pyinstaller pyinstaller.spec
# Produces a folder (dist/MangaReaderTranslate/) rather than a single .exe -
# --onefile is deliberately avoided here: it re-extracts every native DLL
# (torch, onnxruntime-gpu, ctranslate2 are all large) to a temp dir on every
# launch, which is slow and fragile for an app this dependency-heavy.

from PyInstaller.utils.hooks import collect_all

datas = [("resources/fonts", "resources/fonts"), ("resources/icon", "resources/icon")]
binaries = []
hiddenimports = []

for pkg in ("rapidocr", "manga_ocr", "transformers", "ctranslate2", "onnxruntime", "torch", "PySide6", "nvidia"):
    pkg_datas, pkg_binaries, pkg_hiddenimports = collect_all(pkg)
    datas += pkg_datas
    binaries += pkg_binaries
    hiddenimports += pkg_hiddenimports

a = Analysis(
    ["app/main.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="MangaReaderTranslate",
    debug=False,
    strip=False,
    upx=False,
    console=False,
    icon="resources/icon/app.ico",
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="MangaReaderTranslate",
)
