"""pdf2md: aplicación de escritorio para convertir PDF a Markdown.

Paquete con separación clara de responsabilidades:

- :mod:`pdf2md.converter`  -> lógica pura de conversión PDF -> Markdown.
- :mod:`pdf2md.downloader` -> descarga y validación de PDF desde una URL.
- :mod:`pdf2md.gui`        -> interfaz gráfica PySide6 y worker en hilo.
"""

from __future__ import annotations

__version__ = "1.0.0"

__all__ = ["__version__"]
