"""Descarga y validación de PDF desde una URL.

Encapsula el uso de ``httpx`` con tiempos de espera, seguimiento de
redirecciones y validación tanto del ``Content-Type`` como de la firma binaria
del fichero descargado.
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import unquote, urlparse

import httpx

# Tipos MIME aceptados para un PDF. Algunos servidores devuelven variantes.
_PDF_CONTENT_TYPES = frozenset(
    {
        "application/pdf",
        "application/x-pdf",
        "application/acrobat",
        "application/vnd.pdf",
        "text/pdf",
        "text/x-pdf",
        "application/octet-stream",  # fallback común; se valida por firma
    }
)

_PDF_MAGIC = b"%PDF-"

# Límite de tamaño por defecto (en bytes) para evitar descargas abusivas.
DEFAULT_MAX_BYTES = 200 * 1024 * 1024  # 200 MB
DEFAULT_TIMEOUT = 30.0


class DownloadError(Exception):
    """Error genérico durante la descarga del PDF."""


class InvalidURLError(DownloadError):
    """La URL proporcionada no es válida."""


class NotAPDFError(DownloadError):
    """El recurso descargado no es un PDF."""


@dataclass(slots=True, frozen=True)
class DownloadResult:
    """Resultado de una descarga correcta.

    Attributes:
        data: Bytes del PDF descargado.
        source_name: Nombre base (sin extensión) derivado de la URL, útil para
            sugerir el nombre del fichero de salida.
        final_url: URL final tras seguir las redirecciones.
    """

    data: bytes
    source_name: str
    final_url: str


def _validate_url(url: str) -> str:
    """Normaliza y valida una URL HTTP(S).

    Raises:
        InvalidURLError: Si la URL está vacía, mal formada o usa un esquema no
            soportado.
    """
    url = url.strip()
    if not url:
        raise InvalidURLError("La URL está vacía.")

    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise InvalidURLError(
            "La URL debe empezar por 'http://' o 'https://'."
        )
    if not parsed.netloc:
        raise InvalidURLError("La URL no tiene un dominio válido.")
    return url


def _derive_source_name(final_url: str) -> str:
    """Deriva un nombre base razonable a partir de la ruta de la URL."""
    path = urlparse(final_url).path
    last = unquote(path.rsplit("/", 1)[-1]) if path else ""
    if last.lower().endswith(".pdf"):
        last = last[: -len(".pdf")]
    last = last.strip()
    return last or "documento"


def download_pdf(
    url: str,
    *,
    timeout: float = DEFAULT_TIMEOUT,
    max_bytes: int = DEFAULT_MAX_BYTES,
) -> DownloadResult:
    """Descarga un PDF desde ``url`` validando que realmente lo sea.

    Args:
        url: Dirección HTTP(S) del PDF.
        timeout: Tiempo máximo de espera por operación, en segundos.
        max_bytes: Tamaño máximo permitido de la descarga.

    Returns:
        Un :class:`DownloadResult` con los bytes del PDF y metadatos.

    Raises:
        InvalidURLError: Si la URL no es válida.
        NotAPDFError: Si el recurso no es un PDF.
        DownloadError: Ante fallos de red, HTTP o tamaño excedido.
    """
    url = _validate_url(url)

    headers = {
        "User-Agent": "pdf2md/1.0 (+https://example.local)",
        "Accept": "application/pdf,*/*",
    }

    try:
        with httpx.Client(
            follow_redirects=True,
            timeout=timeout,
            headers=headers,
        ) as client:
            with client.stream("GET", url) as response:
                response.raise_for_status()
                final_url = str(response.url)

                content_type = (
                    response.headers.get("content-type", "")
                    .split(";", 1)[0]
                    .strip()
                    .lower()
                )

                # Descarga incremental respetando el límite de tamaño.
                chunks: list[bytes] = []
                total = 0
                for chunk in response.iter_bytes():
                    total += len(chunk)
                    if total > max_bytes:
                        raise DownloadError(
                            "El fichero supera el tamaño máximo permitido "
                            f"({max_bytes // (1024 * 1024)} MB)."
                        )
                    chunks.append(chunk)

    except httpx.HTTPStatusError as exc:
        raise DownloadError(
            f"El servidor respondió con un error HTTP "
            f"{exc.response.status_code}."
        ) from exc
    except httpx.TimeoutException as exc:
        raise DownloadError(
            "La descarga superó el tiempo de espera."
        ) from exc
    except httpx.RequestError as exc:
        raise DownloadError(
            f"No se pudo completar la descarga: {exc}"
        ) from exc

    data = b"".join(chunks)

    if not data:
        raise NotAPDFError("La descarga no devolvió ningún dato.")

    # Validación robusta: la firma binaria manda sobre el Content-Type, que a
    # veces es incorrecto o genérico (octet-stream).
    looks_like_pdf = _PDF_MAGIC in data[:1024]
    content_type_ok = content_type in _PDF_CONTENT_TYPES

    if not looks_like_pdf:
        if not content_type_ok:
            raise NotAPDFError(
                "El recurso no es un PDF "
                f"(Content-Type: '{content_type or 'desconocido'}')."
            )
        raise NotAPDFError(
            "El recurso se anuncia como PDF pero su contenido no lo es."
        )

    return DownloadResult(
        data=data,
        source_name=_derive_source_name(final_url),
        final_url=final_url,
    )
