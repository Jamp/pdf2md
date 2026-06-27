"""Regenera los íconos de la app a partir de assets/logo.svg.

Usa el motor QtSvg (PySide6) porque soporta degradados SVG correctamente
(PyMuPDF no renderiza los degradados con `objectBoundingBox`).

Genera:
- assets/icon_<n>.png en varios tamaños (para QIcon y documentación).
- assets/pdf2md.iconset/ con los tamaños que exige `iconutil` (macOS).
- assets/pdf2md.ico (Windows, multi-tamaño).
- assets/pdf2md.png (Linux, 512 px).

Tras ejecutarlo, construye el .icns de macOS con:
    iconutil -c icns assets/pdf2md.iconset -o assets/pdf2md.icns

Uso:
    QT_QPA_PLATFORM=offscreen .venv/bin/python scripts/render_logo.py
"""

from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QImage, QPainter
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QApplication

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
SVG = ASSETS / "logo.svg"
ICONSET = ASSETS / "pdf2md.iconset"

# Tamaños sueltos para QIcon / documentación.
PNG_SIZES = (1024, 512, 256, 128, 64, 32, 16)
# (tamaño nominal, escala) que exige el formato .iconset de macOS.
ICONSET_SPEC = [
    (16, 1), (16, 2), (32, 1), (32, 2), (128, 1),
    (128, 2), (256, 1), (256, 2), (512, 1), (512, 2),
]


def render(data: QByteArray, size: int, path: Path) -> None:
    renderer = QSvgRenderer(data)
    image = QImage(size, size, QImage.Format_ARGB32)
    image.fill(Qt.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.Antialiasing, True)
    painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
    renderer.render(painter)
    painter.end()
    image.save(str(path))


def main() -> None:
    QApplication.instance() or QApplication([])
    ICONSET.mkdir(parents=True, exist_ok=True)
    data = QByteArray(SVG.read_bytes())

    for size in PNG_SIZES:
        render(data, size, ASSETS / f"icon_{size}.png")

    for nominal, scale in ICONSET_SPEC:
        suffix = "@2x" if scale == 2 else ""
        render(data, nominal * scale, ICONSET / f"icon_{nominal}x{nominal}{suffix}.png")

    # Windows .ico (multi-tamaño) y Linux .png, vía Pillow.
    try:
        from PIL import Image

        ico_path = ASSETS / "pdf2md.ico"
        Image.open(ASSETS / "icon_256.png").save(
            ico_path,
            sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
        )
        # Linux usa un PNG suelto como ícono de ventana/escritorio.
        Image.open(ASSETS / "icon_512.png").save(ASSETS / "pdf2md.png")
        print("Generados pdf2md.ico (Windows) y pdf2md.png (Linux)")
    except ImportError:
        print("Pillow no instalado: omito .ico/.png (pip install pillow)")

    print("Íconos regenerados en", ASSETS)


if __name__ == "__main__":
    main()
