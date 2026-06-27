"""Prueba headless de la lógica de conversión.

Genera un PDF de ejemplo en memoria con PyMuPDF (encabezados, párrafos y una
lista), lo convierte a Markdown con :mod:`pdf2md.converter` y muestra el
resultado. No requiere interfaz gráfica ni red.

Uso:
    .venv/bin/python scripts/smoke_test.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Permite ejecutar el script sin instalar el paquete.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pymupdf  # noqa: E402

from pdf2md.converter import (  # noqa: E402
    InvalidPDFError,
    convert_pdf_bytes,
)


def _build_sample_pdf() -> bytes:
    """Crea un PDF de ejemplo y devuelve sus bytes."""
    doc = pymupdf.open()
    page = doc.new_page()

    # Insertamos texto con distintos tamaños para inducir encabezados.
    page.insert_text((72, 90), "Informe de Prueba", fontsize=24)
    page.insert_text((72, 140), "Sección 1: Introducción", fontsize=18)
    page.insert_text(
        (72, 175),
        "Este es un párrafo de ejemplo para validar la conversión.",
        fontsize=11,
    )
    page.insert_text((72, 210), "Elementos de la lista:", fontsize=11)
    page.insert_text((90, 235), "- Primer elemento", fontsize=11)
    page.insert_text((90, 255), "- Segundo elemento", fontsize=11)
    page.insert_text((90, 275), "- Tercer elemento", fontsize=11)

    data = doc.tobytes()
    doc.close()
    return data


def main() -> int:
    print("== Generando PDF de ejemplo ==")
    pdf_bytes = _build_sample_pdf()
    print(f"PDF generado: {len(pdf_bytes)} bytes")

    print("\n== Convirtiendo a Markdown ==")
    result = convert_pdf_bytes(pdf_bytes, source_name="informe_prueba")
    print(f"Páginas: {result.page_count}")
    print(f"Nombre sugerido: {result.suggested_filename}")
    print("\n----- MARKDOWN -----")
    print(result.markdown)
    print("----- FIN MARKDOWN -----")

    # Comprobaciones básicas.
    assert result.markdown.strip(), "El Markdown no debería estar vacío."
    assert result.page_count == 1
    assert result.suggested_filename == "informe_prueba.md"

    # Comprobamos el manejo de errores con datos no-PDF.
    print("\n== Validando manejo de errores (no es PDF) ==")
    try:
        convert_pdf_bytes(b"esto no es un pdf")
    except InvalidPDFError as exc:
        print(f"OK, error esperado: {exc}")
    else:
        print("FALLO: se esperaba InvalidPDFError")
        return 1

    print("\nTodas las comprobaciones pasaron correctamente.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
