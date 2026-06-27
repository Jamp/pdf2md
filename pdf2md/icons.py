"""Íconos de interfaz monocromos y tintables, basados en Lucide.

Este módulo embebe un puñado de SVG de la familia `Lucide
<https://lucide.dev>`_ como cadenas y los rasteriza a :class:`QIcon` tintados
al color que pida la interfaz. Con ello todos los íconos del *chrome* de la
aplicación (toggle de tema, zona de arrastre, botones de acción…) comparten una
misma familia visual: trazo de 2 px, terminaciones redondeadas y viewBox 24×24,
en lugar de emojis que el sistema renderiza de forma inconsistente.

Íconos de Lucide (https://lucide.dev), licencia ISC. Los SVG se descargaron del
CDN oficial ``https://unpkg.com/lucide-static@latest/icons/<nombre>.svg`` y se
embeben aquí verbatim para no añadir ninguna dependencia de runtime.

Uso típico::

    from pdf2md.icons import lucide_icon

    boton.setIcon(lucide_icon("copy", "#9aa0aa", size=18))
    boton.setIconSize(QSize(18, 18))

Al cambiar de tema basta con volver a llamar a :func:`lucide_icon` con el nuevo
color para regenerar el :class:`QIcon` tintado.
"""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QIcon, QImage, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

# ---------------------------------------------------------------------------
# SVG embebidos. Cada cadena es el contenido oficial de Lucide, con
# ``stroke="currentColor"`` para poder reemplazar el color al tintar. No se
# modifican los trazos: así se conserva la precisión del diseño original.
# ---------------------------------------------------------------------------
_ICONS: dict[str, str] = {
    "sun": (
        '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" '
        'viewBox="0 0 24 24" fill="none" stroke="currentColor" '
        'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
        '<circle cx="12" cy="12" r="4"/>'
        '<path d="M12 2v2"/>'
        '<path d="M12 20v2"/>'
        '<path d="m4.93 4.93 1.41 1.41"/>'
        '<path d="m17.66 17.66 1.41 1.41"/>'
        '<path d="M2 12h2"/>'
        '<path d="M20 12h2"/>'
        '<path d="m6.34 17.66-1.41 1.41"/>'
        '<path d="m19.07 4.93-1.41 1.41"/>'
        "</svg>"
    ),
    "moon": (
        '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" '
        'viewBox="0 0 24 24" fill="none" stroke="currentColor" '
        'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M20.985 12.486a9 9 0 1 1-9.473-9.472c.405-.022.617.46.402'
        ".803a6 6 0 0 0 8.268 8.268c.344-.215.825-.004.803.401\"/>"
        "</svg>"
    ),
    "file-up": (
        '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" '
        'viewBox="0 0 24 24" fill="none" stroke="currentColor" '
        'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M6 22a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h8a2.4 2.4 0 0 1 1.704'
        ".706l3.588 3.588A2.4 2.4 0 0 1 20 8v12a2 2 0 0 1-2 2z\"/>"
        '<path d="M14 2v5a1 1 0 0 0 1 1h5"/>'
        '<path d="M12 12v6"/>'
        '<path d="m15 15-3-3-3 3"/>'
        "</svg>"
    ),
    "link": (
        '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" '
        'viewBox="0 0 24 24" fill="none" stroke="currentColor" '
        'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 '
        '1.71"/>'
        '<path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71'
        '-1.71"/>'
        "</svg>"
    ),
    "arrow-right": (
        '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" '
        'viewBox="0 0 24 24" fill="none" stroke="currentColor" '
        'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M5 12h14"/>'
        '<path d="m12 5 7 7-7 7"/>'
        "</svg>"
    ),
    "copy": (
        '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" '
        'viewBox="0 0 24 24" fill="none" stroke="currentColor" '
        'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
        '<rect width="14" height="14" x="8" y="8" rx="2" ry="2"/>'
        '<path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/>'
        "</svg>"
    ),
    "save": (
        '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" '
        'viewBox="0 0 24 24" fill="none" stroke="currentColor" '
        'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M15.2 3a2 2 0 0 1 1.4.6l3.8 3.8a2 2 0 0 1 .6 1.4V19a2 2 0 '
        '0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2z"/>'
        '<path d="M17 21v-7a1 1 0 0 0-1-1H8a1 1 0 0 0-1 1v7"/>'
        '<path d="M7 3v4a1 1 0 0 0 1 1h7"/>'
        "</svg>"
    ),
}

# Caché de íconos ya generados, indexados por (nombre, color, tamaño). Evita
# rasterizar dos veces el mismo SVG, algo habitual al reconstruir la interfaz o
# al alternar el tema de ida y vuelta.
_ICON_CACHE: dict[tuple[str, str, int], QIcon] = {}


def available_icons() -> tuple[str, ...]:
    """Devuelve los nombres de íconos embebidos disponibles."""
    return tuple(_ICONS)


def _tinted_svg(name: str, color: str) -> bytes:
    """Devuelve el SVG de ``name`` con su ``stroke`` cambiado a ``color``.

    Lucide usa ``stroke="currentColor"``; aquí se sustituye por el color
    concreto del tema para que el rasterizado salga ya tintado.
    """
    try:
        svg = _ICONS[name]
    except KeyError as exc:  # pragma: no cover - error de programación
        raise KeyError(
            f"Ícono Lucide desconocido: {name!r}. "
            f"Disponibles: {', '.join(sorted(_ICONS))}."
        ) from exc
    return svg.replace("currentColor", color).encode("utf-8")


def lucide_icon(name: str, color: str, size: int = 18) -> QIcon:
    """Rasteriza un ícono de Lucide tintado y lo devuelve como :class:`QIcon`.

    El SVG se renderiza con :class:`QSvgRenderer` sobre un :class:`QImage` con
    fondo transparente y antialiasing. Para conseguir nitidez en pantallas HiDPI
    se rasteriza al doble de resolución y se marca el ``devicePixelRatio``, de
    modo que Qt lo presenta al tamaño lógico pedido sin pixelado.

    Args:
        name: Nombre del ícono (uno de :func:`available_icons`).
        color: Color del trazo en formato CSS (p. ej. ``"#9aa0aa"`` o
            ``"white"``). Reemplaza al ``currentColor`` del SVG.
        size: Tamaño lógico en píxeles del lado del ícono cuadrado.

    Returns:
        Un :class:`QIcon` listo para ``setIcon``. Nunca es ``isNull()`` si el
        nombre existe.

    Raises:
        KeyError: Si ``name`` no corresponde a ningún ícono embebido.
    """
    key = (name, color, size)
    cached = _ICON_CACHE.get(key)
    if cached is not None:
        return cached

    data = _tinted_svg(name, color)
    renderer = QSvgRenderer(data)

    scale = 2  # rasterizado @2x para nitidez en HiDPI
    px = size * scale
    image = QImage(px, px, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)

    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
    renderer.render(painter, QRectF(0, 0, px, px))
    painter.end()

    pixmap = QPixmap.fromImage(image)
    pixmap.setDevicePixelRatio(float(scale))

    icon = QIcon(pixmap)
    _ICON_CACHE[key] = icon
    return icon
