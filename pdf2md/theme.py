"""Tema visual de la aplicación: paletas y generación de QSS.

Centraliza todos los colores en una :class:`Palette` y construye la hoja de
estilos (QSS) a partir de ella, de modo que ningún color se repite codificado
a mano por la interfaz. Hay dos paletas listas, :data:`DARK` y :data:`LIGHT`,
con un mismo color de acento índigo para mantener coherencia entre temas.

La función :func:`detect_palette` consulta el esquema de color del sistema con
``QStyleHints.colorScheme()`` (PySide6 6.5+) y elige la paleta adecuada; si no
puede determinarlo, devuelve la oscura por defecto.
"""

from __future__ import annotations

import tempfile
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication


class ThemeMode(str, Enum):
    """Modos de tema disponibles."""

    DARK = "dark"
    LIGHT = "light"


@dataclass(frozen=True, slots=True)
class Palette:
    """Conjunto de colores que define un tema.

    Todos los valores son cadenas hexadecimales (``#rrggbb``). El color de
    acento se reutiliza en el botón primario, el foco de los campos y la barra
    de progreso para dar coherencia visual.
    """

    mode: ThemeMode

    # Fondos y superficies.
    bg: str  # fondo base de la ventana
    surface: str  # tarjetas / paneles
    surface_alt: str  # zonas internas (drop zone, visor)
    border: str  # bordes sutiles
    border_strong: str  # bordes algo más marcados

    # Texto.
    text: str  # texto principal
    text_secondary: str  # texto secundario / subtítulos
    text_muted: str  # texto muy tenue (placeholders, hints)

    # Acento.
    accent: str
    accent_hover: str
    accent_pressed: str
    accent_disabled: str
    accent_text: str  # texto sobre el acento
    accent_soft: str  # acento translúcido para fondos de resalte

    # Componentes auxiliares.
    input_bg: str
    ghost_hover: str  # fondo sutil al pasar por botones "ghost"
    track: str  # canal de la barra de progreso


DARK = Palette(
    mode=ThemeMode.DARK,
    bg="#0f1115",
    surface="#1c2027",
    surface_alt="#15181e",
    border="#2a2f3a",
    border_strong="#3a4150",
    text="#e6e8ec",
    text_secondary="#9aa0aa",
    text_muted="#6b7280",
    accent="#6366f1",
    accent_hover="#7c7ff5",
    accent_pressed="#4f52d4",
    accent_disabled="#3a3d57",
    accent_text="#ffffff",
    accent_soft="rgba(99, 102, 241, 0.16)",
    input_bg="#15181e",
    ghost_hover="rgba(255, 255, 255, 0.06)",
    track="#262b34",
)

LIGHT = Palette(
    mode=ThemeMode.LIGHT,
    bg="#f7f8fa",
    surface="#ffffff",
    surface_alt="#f0f2f5",
    border="#e2e5ea",
    border_strong="#cdd2db",
    text="#1c2027",
    text_secondary="#5b616e",
    text_muted="#9aa0aa",
    accent="#6366f1",
    accent_hover="#5457e0",
    accent_pressed="#4548c4",
    accent_disabled="#c7c9f0",
    accent_text="#ffffff",
    accent_soft="rgba(99, 102, 241, 0.12)",
    input_bg="#ffffff",
    ghost_hover="rgba(99, 102, 241, 0.08)",
    track="#e6e8ec",
)

# Pila de fuentes monoespaciadas preferidas para el visor de Markdown.
_MONO_STACK = '"SF Mono", "JetBrains Mono", "Menlo", "Consolas", monospace'


def detect_palette() -> Palette:
    """Devuelve la paleta que corresponde al esquema del sistema.

    Usa ``QStyleHints.colorScheme()`` cuando está disponible. Ante cualquier
    duda (esquema desconocido o API ausente), devuelve :data:`DARK`.
    """
    app = QGuiApplication.instance()
    if app is not None:
        try:
            scheme = app.styleHints().colorScheme()
        except (AttributeError, RuntimeError):
            scheme = None
        if scheme == Qt.ColorScheme.Light:
            return LIGHT
        if scheme == Qt.ColorScheme.Dark:
            return DARK
    return DARK


# Caché de iconos de tick ya generados, indexados por color, para no escribir
# el mismo SVG en disco más de una vez.
_CHECK_ICON_CACHE: dict[str, str] = {}


def _check_icon(color: str) -> str:
    """Genera (y cachea) un SVG de "tick" del color dado y devuelve su ruta.

    Qt no admite ``data:`` URIs de forma fiable en QSS, así que el icono se
    escribe en un fichero temporal y se referencia por ruta. La ruta se
    normaliza con barras ``/`` para que sea válida dentro de ``url(...)``.
    """
    cached = _CHECK_ICON_CACHE.get(color)
    if cached is not None:
        return cached

    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" '
        'viewBox="0 0 16 16">'
        f'<path d="M3.5 8.5l3 3 6-6.5" fill="none" stroke="{color}" '
        'stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>'
        "</svg>"
    )
    safe = color.lstrip("#") or "fff"
    path = Path(tempfile.gettempdir()) / f"pdf2md_check_{safe}.svg"
    try:
        path.write_text(svg, encoding="utf-8")
    except OSError:
        return ""
    uri = path.as_posix()
    _CHECK_ICON_CACHE[color] = uri
    return uri


def build_qss(p: Palette) -> str:
    """Genera la hoja de estilos completa a partir de una :class:`Palette`.

    Args:
        p: Paleta de colores de la que derivar todos los estilos.

    Returns:
        Una cadena QSS lista para ``QApplication.setStyleSheet``.
    """
    return f"""
/* ----------------------------------------------------------- base */
QWidget {{
    background-color: {p.bg};
    color: {p.text};
    font-size: 14px;
}}

QToolTip {{
    background-color: {p.surface};
    color: {p.text};
    border: 1px solid {p.border};
    border-radius: 6px;
    padding: 4px 8px;
}}

/* --------------------------------------------------------- tipografía */
/* Los labels son siempre transparentes: así no pintan el fondo de la ventana
   sobre las tarjetas, que usan un color de superficie distinto. */
QLabel {{
    background: transparent;
}}

QLabel#appTitle {{
    font-size: 22px;
    font-weight: 700;
    color: {p.text};
}}

QLabel#appSubtitle {{
    font-size: 13px;
    color: {p.text_secondary};
}}

QLabel#sectionLabel {{
    font-size: 12px;
    font-weight: 600;
    color: {p.text_secondary};
}}

QLabel#statusLabel {{
    font-size: 13px;
    color: {p.text_secondary};
}}

/* ------------------------------------------------------------ tarjetas */
QFrame#card {{
    background-color: {p.surface};
    border: 1px solid {p.border};
    border-radius: 12px;
}}

/* ----------------------------------------------------- zona drag & drop */
QFrame#dropZone {{
    background-color: {p.surface_alt};
    border: 2px dashed {p.border_strong};
    border-radius: 12px;
}}

QFrame#dropZone:hover {{
    border-color: {p.accent};
}}

QFrame#dropZone[dragActive="true"] {{
    background-color: {p.accent_soft};
    border-color: {p.accent};
}}

QLabel#dropIcon {{
    font-size: 34px;
    background: transparent;
}}

QLabel#dropTitle {{
    font-size: 15px;
    font-weight: 600;
    color: {p.text};
    background: transparent;
}}

QLabel#dropHint {{
    font-size: 12px;
    color: {p.text_muted};
    background: transparent;
}}

/* -------------------------------------------------------------- botones */
QPushButton {{
    border-radius: 8px;
    padding: 8px 16px;
    font-size: 14px;
    font-weight: 600;
}}

QPushButton#primaryButton {{
    background-color: {p.accent};
    color: {p.accent_text};
    border: none;
}}

QPushButton#primaryButton:hover {{
    background-color: {p.accent_hover};
}}

QPushButton#primaryButton:pressed {{
    background-color: {p.accent_pressed};
}}

QPushButton#primaryButton:disabled {{
    background-color: {p.accent_disabled};
    color: {p.text_muted};
}}

QPushButton#ghostButton {{
    background-color: transparent;
    color: {p.text};
    border: 1px solid {p.border_strong};
}}

QPushButton#ghostButton:hover {{
    background-color: {p.ghost_hover};
    border-color: {p.accent};
}}

QPushButton#ghostButton:pressed {{
    background-color: {p.accent_soft};
}}

QPushButton#ghostButton:disabled {{
    color: {p.text_muted};
    border-color: {p.border};
}}

QPushButton#iconButton {{
    background-color: transparent;
    color: {p.text_secondary};
    border: 1px solid {p.border};
    border-radius: 8px;
    padding: 6px 10px;
    font-size: 16px;
}}

QPushButton#iconButton:hover {{
    background-color: {p.ghost_hover};
    border-color: {p.accent};
    color: {p.text};
}}

/* --------------------------------------------------------------- inputs */
QLineEdit#urlInput {{
    background-color: {p.input_bg};
    color: {p.text};
    border: 1px solid {p.border_strong};
    border-radius: 8px;
    padding: 8px 12px;
    selection-background-color: {p.accent};
    selection-color: {p.accent_text};
}}

QLineEdit#urlInput:focus {{
    border-color: {p.accent};
}}

QLineEdit#urlInput:disabled {{
    color: {p.text_muted};
}}

/* -------------------------------------------------------- checkbox opción */
QCheckBox#optionCheck {{
    background: transparent;
    color: {p.text_secondary};
    font-size: 13px;
    spacing: 9px;
    padding: 2px 0;
}}

QCheckBox#optionCheck:hover {{
    color: {p.text};
}}

QCheckBox#optionCheck::indicator {{
    width: 18px;
    height: 18px;
    border-radius: 6px;
    border: 1px solid {p.border_strong};
    background-color: {p.input_bg};
}}

QCheckBox#optionCheck::indicator:hover {{
    border-color: {p.accent};
}}

QCheckBox#optionCheck::indicator:checked {{
    background-color: {p.accent};
    border-color: {p.accent};
    image: url({_check_icon(p.accent_text)});
}}

QCheckBox#optionCheck::indicator:checked:hover {{
    background-color: {p.accent_hover};
    border-color: {p.accent_hover};
}}

QCheckBox#optionCheck:disabled {{
    color: {p.text_muted};
}}

QCheckBox#optionCheck::indicator:disabled {{
    border-color: {p.border};
    background-color: {p.surface_alt};
}}

/* ----------------------------------------------------- visor markdown */
QPlainTextEdit#markdownView {{
    background-color: {p.surface_alt};
    color: {p.text};
    border: 1px solid {p.border};
    border-radius: 10px;
    padding: 12px;
    font-family: {_MONO_STACK};
    font-size: 13px;
    line-height: 150%;
    selection-background-color: {p.accent};
    selection-color: {p.accent_text};
}}

/* ----------------------------------------------------- barra de progreso */
QProgressBar {{
    background-color: {p.track};
    border: none;
    border-radius: 4px;
    max-height: 8px;
    min-height: 8px;
    text-align: center;
    color: transparent;
}}

QProgressBar::chunk {{
    background-color: {p.accent};
    border-radius: 4px;
}}

/* ----------------------------------------------------------- scrollbar */
QScrollBar:vertical {{
    background: transparent;
    width: 10px;
    margin: 4px 2px 4px 0;
}}

QScrollBar::handle:vertical {{
    background: {p.border_strong};
    border-radius: 4px;
    min-height: 28px;
}}

QScrollBar::handle:vertical:hover {{
    background: {p.text_muted};
}}

QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {{
    height: 0;
}}

QScrollBar::add-page:vertical,
QScrollBar::sub-page:vertical {{
    background: transparent;
}}
"""
