"""Interfaz gráfica PySide6 para pdf2md.

Contiene la ventana principal y un worker que ejecuta la descarga y/o la
conversión en un :class:`QThread`, de modo que la interfaz nunca se congela.
La lógica de negocio vive en :mod:`pdf2md.converter` y
:mod:`pdf2md.downloader`; aquí solo se orquesta y se presenta.

El aspecto visual (tema claro/oscuro automático, colores y QSS) se delega en
:mod:`pdf2md.theme`, que centraliza la paleta y genera la hoja de estilos.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import (
    QMimeData,
    QObject,
    Qt,
    QThread,
    Signal,
)
from PySide6.QtGui import (
    QDragEnterEvent,
    QDragLeaveEvent,
    QDropEvent,
    QGuiApplication,
    QIcon,
    QMouseEvent,
)
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from pdf2md import __version__
from pdf2md.converter import (
    ConversionError,
    ConversionResult,
    convert_pdf_bytes,
    convert_pdf_path,
)
from pdf2md.downloader import DownloadError, download_pdf
from pdf2md.theme import (
    DARK,
    LIGHT,
    Palette,
    ThemeMode,
    build_qss,
    detect_palette,
)


def _asset(name: str) -> Path:
    """Devuelve la ruta a un recurso de ``assets/``.

    Resuelve la base tanto en desarrollo (raíz del proyecto) como dentro de un
    bundle de PyInstaller, que extrae los datos en ``sys._MEIPASS``.
    """
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    return base / "assets" / name


def _app_icon() -> QIcon:
    """Construye el :class:`QIcon` de la aplicación desde ``assets/logo.svg``.

    PySide6 incluye el plugin SVG, por lo que ``QIcon`` renderiza el SVG nítido
    a cualquier tamaño. Si el fichero no existe, degrada con elegancia
    devolviendo un :class:`QIcon` vacío sin romper la interfaz.
    """
    logo = _asset("logo.svg")
    if logo.is_file():
        return QIcon(str(logo))
    return QIcon()


def _is_local_pdf(mime: QMimeData) -> str | None:
    """Devuelve la ruta del primer PDF local presente en ``mime``, o ``None``."""
    if not mime.hasUrls():
        return None
    for qurl in mime.urls():
        if not qurl.isLocalFile():
            continue
        local = qurl.toLocalFile()
        if local.lower().endswith(".pdf"):
            return local
    return None


class ConversionWorker(QObject):
    """Worker que realiza la conversión en segundo plano.

    Se mueve a un :class:`QThread` mediante ``moveToThread``. Emite
    :attr:`finished` con el resultado o :attr:`failed` con un mensaje de error
    legible para el usuario.
    """

    progress = Signal(str)
    finished = Signal(object)  # ConversionResult
    failed = Signal(str)

    def __init__(
        self,
        *,
        file_path: str | None = None,
        url: str | None = None,
        strip_repeated_headers: bool = True,
    ) -> None:
        super().__init__()
        self._file_path = file_path
        self._url = url
        self._strip_repeated_headers = strip_repeated_headers

    def run(self) -> None:
        """Ejecuta la tarea. Pensado para conectarse a ``QThread.started``."""
        try:
            result = self._do_work()
        except (ConversionError, DownloadError) as exc:
            self.failed.emit(str(exc))
        except Exception as exc:  # red de seguridad ante fallos imprevistos
            self.failed.emit(f"Error inesperado: {exc}")
        else:
            self.finished.emit(result)

    def _do_work(self) -> ConversionResult:
        if self._url is not None:
            self.progress.emit("Descargando PDF…")
            download = download_pdf(self._url)
            self.progress.emit("Convirtiendo a Markdown…")
            return convert_pdf_bytes(
                download.data,
                source_name=download.source_name,
                strip_repeated_headers=self._strip_repeated_headers,
            )

        if self._file_path is not None:
            self.progress.emit("Convirtiendo a Markdown…")
            return convert_pdf_path(
                self._file_path,
                strip_repeated_headers=self._strip_repeated_headers,
            )

        raise ConversionError("No se indicó ni un fichero ni una URL.")


class DropZone(QFrame):
    """Zona destacada para arrastrar y soltar (o clicar para elegir) un PDF.

    Resalta su borde y fondo con el color de acento mientras se arrastra un
    PDF por encima, mediante la propiedad dinámica ``dragActive`` y un
    repolish del estilo. Emite :attr:`clicked` al pulsar y
    :attr:`pdfDropped` con la ruta cuando se suelta un PDF válido.
    """

    clicked = Signal()
    pdfDropped = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("dropZone")
        self.setAcceptDrops(True)
        self.setProperty("dragActive", False)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(132)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(4)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        icon = QLabel("📄")
        icon.setObjectName("dropIcon")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)

        title = QLabel("Arrastra un PDF aquí")
        title.setObjectName("dropTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        hint = QLabel("o haz clic para elegir un archivo")
        hint.setObjectName("dropHint")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(icon)
        layout.addWidget(title)
        layout.addWidget(hint)

    def setEnabled(self, enabled: bool) -> None:  # noqa: D102
        super().setEnabled(enabled)
        self.setCursor(
            Qt.CursorShape.PointingHandCursor
            if enabled
            else Qt.CursorShape.ArrowCursor
        )

    # ------------------------------------------------------------ resaltado
    def _set_drag_active(self, active: bool) -> None:
        self.setProperty("dragActive", active)
        self.style().unpolish(self)
        self.style().polish(self)

    # -------------------------------------------------------------- eventos
    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self.isEnabled() and event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:  # noqa: N802
        if self.isEnabled() and _is_local_pdf(event.mimeData()) is not None:
            self._set_drag_active(True)
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragLeaveEvent(self, event: QDragLeaveEvent) -> None:  # noqa: N802
        self._set_drag_active(False)
        super().dragLeaveEvent(event)

    def dropEvent(self, event: QDropEvent) -> None:  # noqa: N802
        self._set_drag_active(False)
        path = _is_local_pdf(event.mimeData())
        if path is None or not self.isEnabled():
            event.ignore()
            return
        event.acceptProposedAction()
        self.pdfDropped.emit(path)


class MainWindow(QMainWindow):
    """Ventana principal de la aplicación."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"pdf2md {__version__} — PDF a Markdown")
        self.setWindowIcon(_app_icon())
        self.resize(820, 640)
        self.setMinimumSize(640, 540)
        self.setAcceptDrops(True)

        self._thread: QThread | None = None
        self._worker: ConversionWorker | None = None
        self._result: ConversionResult | None = None
        self._palette: Palette = detect_palette()

        self._build_ui()
        self._apply_theme()
        self._set_busy(False)

    # ------------------------------------------------------------------ UI
    def _build_ui(self) -> None:
        central = QWidget(self)
        root = QVBoxLayout(central)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(16)

        root.addLayout(self._build_header())
        root.addWidget(self._build_input_card())
        root.addWidget(self._build_output_card(), 1)
        root.addLayout(self._build_status_row())

        self.setCentralWidget(central)

    def _build_header(self) -> QHBoxLayout:
        header = QHBoxLayout()
        header.setSpacing(12)

        titles = QVBoxLayout()
        titles.setSpacing(2)
        title = QLabel("PDF → Markdown")
        title.setObjectName("appTitle")
        subtitle = QLabel(
            "Convierte documentos PDF a Markdown limpio y reutilizable."
        )
        subtitle.setObjectName("appSubtitle")
        titles.addWidget(title)
        titles.addWidget(subtitle)

        self.btn_theme = QPushButton()
        self.btn_theme.setObjectName("iconButton")
        self.btn_theme.setToolTip("Cambiar entre tema claro y oscuro")
        self.btn_theme.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_theme.clicked.connect(self._toggle_theme)

        header.addLayout(titles, 1)
        header.addWidget(self.btn_theme, 0, Qt.AlignmentFlag.AlignTop)
        return header

    def _build_input_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 18, 20, 20)
        layout.setSpacing(14)

        # Zona de arrastrar y soltar.
        self.drop_zone = DropZone()
        self.drop_zone.clicked.connect(self._on_open_file)
        self.drop_zone.pdfDropped.connect(
            lambda path: self._start_conversion(file_path=path)
        )
        layout.addWidget(self.drop_zone)

        # Separador "o desde una URL".
        url_label = QLabel("🔗  Desde una URL")
        url_label.setObjectName("sectionLabel")
        layout.addWidget(url_label)

        url_row = QHBoxLayout()
        url_row.setSpacing(10)
        self.url_edit = QLineEdit()
        self.url_edit.setObjectName("urlInput")
        self.url_edit.setClearButtonEnabled(True)
        self.url_edit.setPlaceholderText(
            "https://ejemplo.com/documento.pdf"
        )
        self.url_edit.returnPressed.connect(self._on_convert_url)
        self.btn_url = QPushButton("Convertir")
        self.btn_url.setObjectName("primaryButton")
        self.btn_url.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_url.clicked.connect(self._on_convert_url)
        url_row.addWidget(self.url_edit, 1)
        url_row.addWidget(self.btn_url)
        layout.addLayout(url_row)

        # Opción de limpieza: eliminar encabezados/pies repetidos.
        self.chk_strip = QCheckBox("Eliminar encabezados/pies repetidos")
        self.chk_strip.setObjectName("optionCheck")
        self.chk_strip.setChecked(True)
        self.chk_strip.setCursor(Qt.CursorShape.PointingHandCursor)
        self.chk_strip.setToolTip(
            "Detecta y quita las líneas que se repiten en casi todas las "
            "páginas (pies corporativos, numeración…)."
        )
        layout.addWidget(self.chk_strip)

        return card

    def _build_output_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 18, 20, 20)
        layout.setSpacing(12)

        head = QHBoxLayout()
        out_label = QLabel("Resultado")
        out_label.setObjectName("sectionLabel")
        head.addWidget(out_label)
        head.addStretch(1)

        self.btn_copy = QPushButton("📋  Copiar")
        self.btn_copy.setObjectName("ghostButton")
        self.btn_copy.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_copy.clicked.connect(self._on_copy)
        self.btn_save = QPushButton("💾  Guardar .md")
        self.btn_save.setObjectName("ghostButton")
        self.btn_save.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_save.clicked.connect(self._on_save)
        head.addWidget(self.btn_copy)
        head.addWidget(self.btn_save)
        layout.addLayout(head)

        self.output = QPlainTextEdit()
        self.output.setObjectName("markdownView")
        self.output.setReadOnly(True)
        self.output.setPlaceholderText(
            "El Markdown convertido aparecerá aquí…"
        )
        layout.addWidget(self.output, 1)

        return card

    def _build_status_row(self) -> QHBoxLayout:
        status_row = QHBoxLayout()
        status_row.setSpacing(12)
        self.status = QLabel("Listo.")
        self.status.setObjectName("statusLabel")
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)  # modo indeterminado
        self.progress.setTextVisible(False)
        self.progress.setVisible(False)
        self.progress.setFixedWidth(160)
        status_row.addWidget(self.status, 1)
        status_row.addWidget(self.progress)
        return status_row

    # -------------------------------------------------------------- tema
    def _apply_theme(self) -> None:
        """Aplica el QSS de la paleta actual a toda la aplicación."""
        app = QApplication.instance()
        if app is not None:
            app.setStyleSheet(build_qss(self._palette))
        # Icono coherente: luna cuando está oscuro (clic -> claro) y sol al revés.
        self.btn_theme.setText(
            "☀" if self._palette.mode is ThemeMode.DARK else "🌙"
        )

    def _toggle_theme(self) -> None:
        self._palette = (
            LIGHT if self._palette.mode is ThemeMode.DARK else DARK
        )
        self._apply_theme()

    # -------------------------------------------------------------- estado
    def _set_busy(self, busy: bool) -> None:
        """Habilita o deshabilita controles según haya tarea en curso."""
        self.drop_zone.setEnabled(not busy)
        self.btn_url.setEnabled(not busy)
        self.url_edit.setEnabled(not busy)
        self.chk_strip.setEnabled(not busy)
        self.progress.setVisible(busy)
        has_result = self._result is not None
        self.btn_save.setEnabled(not busy and has_result)
        self.btn_copy.setEnabled(not busy and has_result)

    def _set_status(self, text: str) -> None:
        self.status.setText(text)

    # ----------------------------------------------------------- acciones
    def _on_open_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Seleccionar PDF",
            str(Path.home()),
            "Documentos PDF (*.pdf)",
        )
        if path:
            self._start_conversion(file_path=path)

    def _on_convert_url(self) -> None:
        url = self.url_edit.text().strip()
        if not url:
            self._warn("Introduce una URL antes de convertir.")
            return
        self._start_conversion(url=url)

    def _on_save(self) -> None:
        if self._result is None:
            return
        default_dir = Path.home() / self._result.suggested_filename
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Guardar Markdown",
            str(default_dir),
            "Markdown (*.md);;Todos los archivos (*)",
        )
        if not path:
            return
        try:
            Path(path).write_text(self._result.markdown, encoding="utf-8")
        except OSError as exc:
            self._warn(f"No se pudo guardar el fichero:\n{exc}")
            return
        self._set_status(f"Guardado en {path}")

    def _on_copy(self) -> None:
        if self._result is None:
            return
        clipboard = QGuiApplication.clipboard()
        mime = QMimeData()
        mime.setText(self._result.markdown)
        clipboard.setMimeData(mime)
        self._set_status("Markdown copiado al portapapeles.")

    # -------------------------------------------------------- worker/hilo
    def _start_conversion(
        self,
        *,
        file_path: str | None = None,
        url: str | None = None,
    ) -> None:
        if self._thread is not None:
            return  # ya hay una tarea en curso

        self._result = None
        self.output.clear()
        self._set_busy(True)
        self._set_status("Procesando…")

        self._thread = QThread(self)
        self._worker = ConversionWorker(
            file_path=file_path,
            url=url,
            strip_repeated_headers=self.chk_strip.isChecked(),
        )
        self._worker.moveToThread(self._thread)

        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(self._set_status)
        self._worker.finished.connect(self._on_worker_finished)
        self._worker.failed.connect(self._on_worker_failed)

        # Limpieza ordenada del hilo cuando termina (éxito o fallo).
        self._worker.finished.connect(self._thread.quit)
        self._worker.failed.connect(self._thread.quit)
        self._thread.finished.connect(self._cleanup_thread)

        self._thread.start()

    def _on_worker_finished(self, result: ConversionResult) -> None:
        self._result = result
        self.output.setPlainText(result.markdown)
        self._set_status(
            f"Listo. {result.page_count} página(s) convertidas."
        )

    def _on_worker_failed(self, message: str) -> None:
        self._set_status("Error en la conversión.")
        self._warn(message)

    def _cleanup_thread(self) -> None:
        if self._worker is not None:
            self._worker.deleteLater()
        if self._thread is not None:
            self._thread.deleteLater()
        self._worker = None
        self._thread = None
        self._set_busy(False)

    # ----------------------------------------------------- drag and drop
    # La ventana también acepta drops en cualquier zona como comodidad; la
    # :class:`DropZone` añade el resaltado visual al pasar por encima de ella.
    def dragEnterEvent(self, event: QDragEnterEvent) -> None:  # noqa: N802
        if self._thread is None and _is_local_pdf(event.mimeData()) is not None:
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent) -> None:  # noqa: N802
        path = _is_local_pdf(event.mimeData())
        if path is None or self._thread is not None:
            event.ignore()
            return
        event.acceptProposedAction()
        self._start_conversion(file_path=path)

    # ------------------------------------------------------------ helpers
    def _warn(self, message: str) -> None:
        QMessageBox.warning(self, "pdf2md", message)


def main() -> int:
    """Punto de entrada de la aplicación gráfica."""
    app = QApplication(sys.argv)
    app.setApplicationName("pdf2md")
    app.setApplicationDisplayName("pdf2md")
    app.setWindowIcon(_app_icon())
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
