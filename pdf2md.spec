# -*- mode: python ; coding: utf-8 -*-
"""Especificación multiplataforma de PyInstaller para empaquetar pdf2md.

Ramifica por ``sys.platform``:

- **macOS (darwin):** genera ``dist/pdf2md.app`` (onedir + windowed + BUNDLE),
  ícono ``assets/pdf2md.icns``.
- **Windows (win32):** genera ``dist/pdf2md/`` (onedir + windowed),
  ícono ``assets/pdf2md.ico``.
- **Linux:** genera ``dist/pdf2md/`` (onedir + windowed), sin ícono embebido
  en el ejecutable (se usa ``assets/pdf2md.png`` en el ``.desktop``/AppImage).

Build reproducible en cualquiera de los tres sistemas:
    pyinstaller --noconfirm --clean pdf2md.spec

En macOS también se puede usar el atajo: ./scripts/build_macos.sh
"""

import sys

from PyInstaller.utils.hooks import collect_all

IS_MACOS = sys.platform == "darwin"
IS_WINDOWS = sys.platform == "win32"

# Ícono según el sistema operativo (None en Linux: el ejecutable no embebe
# ícono; el escritorio usa assets/pdf2md.png vía el .desktop / AppImage).
if IS_MACOS:
    ICON = "assets/pdf2md.icns"
elif IS_WINDOWS:
    ICON = "assets/pdf2md.ico"
else:
    ICON = None

# La carpeta assets/ se embebe completa (logo.svg se carga en runtime vía
# sys._MEIPASS desde el helper _asset() de pdf2md/gui.py). Usamos una tupla
# (origen, destino) -> PyInstaller aplica el separador correcto por SO; NO
# usamos ':' ni ';' literales.
datas = [("assets", "assets")]
binaries = []
hiddenimports = []

# Paquetes que arrastran datos/binarios que los hooks por defecto no
# recogen completos (modelos .onnx de pymupdf-layout, dylibs/so de MuPDF,
# bibliotecas nativas de onnxruntime).
for pkg in ("pymupdf", "pymupdf4llm", "onnxruntime", "numpy"):
    pkg_datas, pkg_binaries, pkg_hiddenimports = collect_all(pkg)
    datas += pkg_datas
    binaries += pkg_binaries
    hiddenimports += pkg_hiddenimports

block_cipher = None


a = Analysis(
    ["pdf2md/__main__.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Módulos de PySide6 que la app no usa; reducen el tamaño sin
        # afectar la funcionalidad (GUI sencilla + SVG para el ícono).
        "PySide6.QtWebEngineCore",
        "PySide6.QtWebEngineWidgets",
        "PySide6.QtWebEngineQuick",
        "PySide6.Qt3DCore",
        "PySide6.Qt3DRender",
        "PySide6.QtMultimedia",
        "PySide6.QtMultimediaWidgets",
        "PySide6.QtCharts",
        "PySide6.QtDataVisualization",
        "tkinter",
    ],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="pdf2md",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,  # equivale a --windowed
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=ICON,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="pdf2md",
)

# El BUNDLE (.app) solo tiene sentido en macOS. En Windows/Linux la salida
# es la carpeta onedir 'dist/pdf2md/' producida por COLLECT.
if IS_MACOS:
    app = BUNDLE(
        coll,
        name="pdf2md.app",
        icon="assets/pdf2md.icns",
        bundle_identifier="com.jamp.pdf2md",
        info_plist={
            "CFBundleName": "pdf2md",
            "CFBundleDisplayName": "pdf2md",
            "CFBundleShortVersionString": "1.0.0",
            "CFBundleVersion": "1.0.0",
            "NSHighResolutionCapable": True,
            "LSMinimumSystemVersion": "11.0",
        },
    )
