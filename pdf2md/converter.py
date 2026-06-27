"""Lógica pura de conversión de PDF a Markdown.

Este módulo no depende de la interfaz gráfica: recibe bytes o una ruta de un
PDF y devuelve el Markdown resultante usando ``pymupdf4llm``. Así puede
probarse de forma headless y reutilizarse en cualquier contexto.
"""

from __future__ import annotations

import math
import os
import re
import tempfile
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

import pymupdf  # PyMuPDF
import pymupdf4llm

# Firma binaria estándar de un fichero PDF.
_PDF_MAGIC = b"%PDF-"

# --- Filtro de encabezados/pies repetidos -------------------------------------
# Umbral por defecto: una línea se considera encabezado/pie si aparece (tras
# normalizarla) en al menos este porcentaje de las páginas del documento.
_DEFAULT_HEADER_THRESHOLD = 0.6
# El filtro solo se activa a partir de este número de páginas: en documentos
# muy cortos la repetición no es estadísticamente fiable.
_MIN_PAGES_FOR_STRIP = 3
# Solo se consideran candidatas las líneas "cortas": así jamás se elimina un
# párrafo largo legítimo que casualmente se repita.
_HEADER_MAX_LEN = 90

_WS_RE = re.compile(r"\s+")
_BLANK_RUN_RE = re.compile(r"\n{3,}")
# Caracteres de formato Markdown que se ignoran al normalizar (negritas,
# cursivas, código, encabezados y citas), para que "**Pie**" case con "Pie".
_MD_STRIP_CHARS = "*_`#>~ "
# Marcador único para agrupar cualquier línea que sea solo un número de página
# ("12", "Página 3 de 37", "3 / 37", "- 4 -", …) en un mismo cubo.
_PAGENUM_BUCKET = "\x00pagenum"
_PAGENUM_PATTERNS = (
    re.compile(r"^\d{1,4}$"),
    re.compile(r"^p[áa]g(?:ina)?\.?\s*\d{1,4}(?:\s*(?:de|/)\s*\d{1,4})?$"),
    re.compile(r"^\d{1,4}\s*/\s*\d{1,4}$"),
    re.compile(r"^[-–—]\s*\d{1,4}\s*[-–—]$"),
)


def _normalize_line(line: str) -> str:
    """Normaliza una línea para comparar repeticiones entre páginas.

    Quita espacios y marcas de Markdown de los extremos, colapsa los espacios
    internos, pasa a minúsculas y agrupa los números de página en un único
    cubo. Devuelve cadena vacía para líneas en blanco.
    """
    s = line.strip().strip(_MD_STRIP_CHARS).strip()
    s = _WS_RE.sub(" ", s)
    if not s:
        return ""
    low = s.lower()
    for pat in _PAGENUM_PATTERNS:
        if pat.match(low):
            return _PAGENUM_BUCKET
    return low


# Longitud mínima (en caracteres) de un pie textual para permitir eliminarlo
# también cuando aparece incrustado al final de una línea de contenido. Evita
# tocar fragmentos cortos que podrían formar parte legítima de un párrafo.
_EMBEDDED_FOOTER_MIN_LEN = 20


def _repeated_header_lines(
    pages: list[str], threshold: float
) -> tuple[set[str], set[str]]:
    """Detecta las líneas que se repiten como encabezado/pie.

    Una línea es repetida si su forma normalizada (corta) aparece en al menos
    ``ceil(num_páginas * threshold)`` páginas distintas.

    Returns:
        Una tupla ``(claves, literales)``:

        - ``claves``: formas normalizadas consideradas encabezado/pie. Se usan
          para eliminar líneas que son *íntegramente* un encabezado/pie.
        - ``literales``: textos literales (colapsados) de los pies puramente
          textuales y suficientemente largos. Se usan para eliminar el pie
          cuando el extractor lo ha pegado al final de una línea de contenido.
    """
    page_count = len(pages)
    pages_with_line: dict[str, set[int]] = defaultdict(set)
    literals_by_key: dict[str, set[str]] = defaultdict(set)
    for idx, text in enumerate(pages):
        for raw in text.splitlines():
            norm = _normalize_line(raw)
            if not norm:
                continue
            if norm != _PAGENUM_BUCKET and len(norm) > _HEADER_MAX_LEN:
                continue
            pages_with_line[norm].add(idx)
            collapsed = _WS_RE.sub(" ", raw.strip())
            literals_by_key[norm].add(collapsed)

    min_pages = max(2, math.ceil(page_count * threshold))
    keys = {
        norm
        for norm, page_idxs in pages_with_line.items()
        if len(page_idxs) >= min_pages
    }

    literals: set[str] = set()
    for norm in keys:
        if norm == _PAGENUM_BUCKET:
            continue  # nunca borrar dígitos sueltos dentro de otras líneas
        for literal in literals_by_key[norm]:
            if len(literal) >= _EMBEDDED_FOOTER_MIN_LEN:
                literals.add(literal)
    return keys, literals


def _embedded_footer_pattern(literals: set[str]) -> re.Pattern[str] | None:
    """Compila un patrón que casa cualquiera de los pies ``literals``.

    El emparejamiento es flexible con los espacios (uno o más entre palabras)
    para tolerar variaciones de extracción. Devuelve ``None`` si no hay
    literales.
    """
    if not literals:
        return None
    # Los más largos primero para que la alternancia prefiera el match completo.
    alts = sorted(literals, key=len, reverse=True)
    parts = [r"\s+".join(re.escape(w) for w in lit.split()) for lit in alts]
    return re.compile("(?:" + "|".join(parts) + r")\s*")


def _strip_repeated_headers(pages: list[str], threshold: float) -> str:
    """Reconstruye el Markdown eliminando los encabezados/pies repetidos.

    Args:
        pages: Texto Markdown de cada página (de ``page_chunks=True``).
        threshold: Fracción mínima de páginas en las que debe aparecer una
            línea para considerarla encabezado/pie.

    Returns:
        El Markdown combinado y limpio, sin las líneas repetidas y sin
        acumulaciones de líneas en blanco sobrantes.
    """
    repeated, literals = _repeated_header_lines(pages, threshold)
    embedded = _embedded_footer_pattern(literals)

    cleaned_pages: list[str] = []
    for text in pages:
        kept: list[str] = []
        for line in text.splitlines():
            norm = _normalize_line(line)
            if norm in repeated:
                continue  # la línea entera es un encabezado/pie repetido
            if embedded is not None and norm not in repeated:
                # Quita el pie si quedó pegado al final de una línea de
                # contenido; el resto del texto legítimo se conserva.
                line = embedded.sub(" ", line).rstrip()
            kept.append(line)
        cleaned_pages.append("\n".join(kept))

    combined = "\n\n".join(cleaned_pages)
    combined = _BLANK_RUN_RE.sub("\n\n", combined)
    return combined.strip() + "\n"


class ConversionError(Exception):
    """Error genérico durante la conversión de un PDF a Markdown."""


class InvalidPDFError(ConversionError):
    """El contenido proporcionado no es un PDF válido o está corrupto."""


@dataclass(slots=True, frozen=True)
class ConversionResult:
    """Resultado de una conversión.

    Attributes:
        markdown: Texto Markdown generado.
        page_count: Número de páginas procesadas del PDF.
        source_name: Nombre base sugerido para el fichero de salida
            (sin extensión), derivado del origen del PDF.
    """

    markdown: str
    page_count: int
    source_name: str

    @property
    def suggested_filename(self) -> str:
        """Nombre de fichero ``.md`` sugerido para guardar el resultado."""
        return f"{self.source_name}.md"


def _looks_like_pdf(data: bytes) -> bool:
    """Comprueba de forma barata si ``data`` empieza por la firma de un PDF.

    Algunos PDF incluyen bytes basura o un BOM antes de la cabecera, por lo
    que se busca la firma dentro de los primeros 1024 bytes.
    """
    return _PDF_MAGIC in data[:1024]


def convert_pdf_bytes(
    data: bytes,
    *,
    source_name: str = "documento",
    strip_repeated_headers: bool = True,
    header_threshold: float = _DEFAULT_HEADER_THRESHOLD,
) -> ConversionResult:
    """Convierte los bytes de un PDF a Markdown.

    Args:
        data: Contenido binario completo del PDF.
        source_name: Nombre base (sin extensión) para sugerir el fichero de
            salida.
        strip_repeated_headers: Si es ``True`` (por defecto), detecta y elimina
            las líneas de encabezado/pie que se repiten en casi todas las
            páginas (p. ej. un pie corporativo o la numeración de página). Solo
            actúa en documentos de al menos :data:`_MIN_PAGES_FOR_STRIP`
            páginas y nunca toca líneas largas, para no borrar contenido
            legítimo.
        header_threshold: Fracción mínima de páginas (0–1) en las que debe
            aparecer una línea para considerarla encabezado/pie repetido.

    Returns:
        Un :class:`ConversionResult` con el Markdown y metadatos.

    Raises:
        InvalidPDFError: Si los datos no parecen un PDF o no pueden abrirse.
        ConversionError: Ante cualquier otro fallo durante la conversión.

    Example:
        >>> md = convert_pdf_bytes(pdf_bytes, source_name="informe").markdown
    """
    if not data:
        raise InvalidPDFError("El PDF está vacío (0 bytes).")

    if not _looks_like_pdf(data):
        raise InvalidPDFError(
            "El contenido no parece un PDF válido (falta la cabecera '%PDF-')."
        )

    # Abrimos desde memoria para validar la estructura antes de convertir.
    try:
        doc = pymupdf.open(stream=data, filetype="pdf")
    except Exception as exc:  # pymupdf lanza distintos tipos según el fallo
        raise InvalidPDFError(f"No se pudo abrir el PDF: {exc}") from exc

    try:
        if doc.needs_pass:
            raise InvalidPDFError(
                "El PDF está protegido con contraseña y no puede convertirse."
            )
        page_count = doc.page_count
        if page_count == 0:
            raise InvalidPDFError("El PDF no contiene páginas.")
    finally:
        doc.close()

    # pymupdf4llm.to_markdown acepta una ruta o un documento ya abierto.
    # Escribimos a un temporal para no depender de detalles internos de la API
    # y garantizar compatibilidad entre versiones.
    tmp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            suffix=".pdf", delete=False
        ) as tmp:
            tmp.write(data)
            tmp_path = Path(tmp.name)

        if strip_repeated_headers and page_count >= _MIN_PAGES_FOR_STRIP:
            # page_chunks=True devuelve una lista de dicts, uno por página,
            # con el Markdown de la página en la clave 'text'. Lo usamos para
            # contar repeticiones por página y filtrar encabezados/pies.
            chunks = pymupdf4llm.to_markdown(str(tmp_path), page_chunks=True)
            pages = [str(chunk.get("text", "")) for chunk in chunks]
            threshold = min(max(header_threshold, 0.0), 1.0)
            markdown = _strip_repeated_headers(pages, threshold)
        else:
            markdown = pymupdf4llm.to_markdown(str(tmp_path))
    except InvalidPDFError:
        raise
    except Exception as exc:
        raise ConversionError(
            f"Fallo durante la conversión a Markdown: {exc}"
        ) from exc
    finally:
        if tmp_path is not None:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    return ConversionResult(
        markdown=markdown,
        page_count=page_count,
        source_name=source_name or "documento",
    )


def convert_pdf_path(
    path: str | os.PathLike[str],
    *,
    strip_repeated_headers: bool = True,
    header_threshold: float = _DEFAULT_HEADER_THRESHOLD,
) -> ConversionResult:
    """Convierte un PDF en disco a Markdown.

    Args:
        path: Ruta al fichero PDF.
        strip_repeated_headers: Igual que en :func:`convert_pdf_bytes`.
        header_threshold: Igual que en :func:`convert_pdf_bytes`.

    Returns:
        Un :class:`ConversionResult` con el Markdown y metadatos. El
        ``source_name`` se deriva del nombre del fichero.

    Raises:
        InvalidPDFError: Si la ruta no existe, no es un fichero o no es un PDF.
        ConversionError: Ante cualquier otro fallo durante la conversión.
    """
    p = Path(path)
    if not p.exists():
        raise InvalidPDFError(f"El fichero no existe: {p}")
    if not p.is_file():
        raise InvalidPDFError(f"La ruta no es un fichero: {p}")

    try:
        data = p.read_bytes()
    except OSError as exc:
        raise ConversionError(f"No se pudo leer el fichero: {exc}") from exc

    return convert_pdf_bytes(
        data,
        source_name=p.stem,
        strip_repeated_headers=strip_repeated_headers,
        header_threshold=header_threshold,
    )
