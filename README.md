# pdf2md

> Conversor de escritorio ligero y rápido de PDF a Markdown — soporta archivos
> locales y URLs.

**pdf2md** es una aplicación de escritorio multiplataforma (macOS, Windows y
Linux) para **convertir PDF a Markdown** de alta calidad, conservando
encabezados, listas y tablas. Está construida con **PySide6** (Qt nativo) y
**pymupdf4llm** sobre **PyMuPDF**, con una interfaz moderna y un motor de
conversión que se ejecuta en un hilo de trabajo para que la UI nunca se
congele.

- **Entrada flexible:** archivo PDF local (selector o arrastrar y soltar) o una
  URL que apunta a un PDF.
- **Conversión de alta calidad** con `pymupdf4llm` (encabezados, listas, tablas).
- **Filtro de encabezados/pies repetidos** para limpiar pies corporativos y
  numeración de página.
- **Tema claro/oscuro** automático según el sistema, con conmutador manual.
- **Multiplataforma:** bundles nativos para macOS (`.app`), Windows y Linux.

## Características

- Acepta dos tipos de entrada:
  - Un archivo PDF local (selector de archivos y **arrastrar y soltar**).
  - Una **URL** que apunta a un PDF (lo descarga, valida y convierte).
- Conversión a Markdown con `pymupdf4llm` (encabezados, listas, tablas).
- **Filtro de encabezados/pies repetidos** (activado por defecto): detecta las
  líneas que se repiten en casi todas las páginas (pies corporativos como
  «Datos elaborados por … para uso Interno», numeración de página, etc.) y las
  elimina del Markdown. Se controla con la casilla **«Eliminar encabezados/pies
  repetidos»** de la interfaz y con el parámetro `strip_repeated_headers` de
  `convert_pdf_bytes` / `convert_pdf_path`. Es conservador: solo actúa en
  documentos de ≥ 3 páginas, sobre líneas cortas que aparecen en ≥ 60 % de las
  páginas, por lo que **no borra** títulos ni cláusulas que aparecen una sola
  vez.
- Visor del Markdown resultante con opción de:
  - **Guardar** el `.md` en disco (nombre por defecto basado en el PDF).
  - **Copiar al portapapeles**.
- La conversión se ejecuta en un **hilo de trabajo** (`QThread`), por lo que la
  interfaz nunca se congela; incluye indicador de estado y progreso.
- **Manejo de errores claro y visible**: URL inválida, descarga fallida,
  recurso que no es un PDF, PDF corrupto o protegido con contraseña, etc.

## Diseño

Interfaz moderna inspirada en apps de productividad (estilo Linear / Raycast),
con estética pulida en lugar de un formulario Qt por defecto:

- **Tema claro y oscuro automáticos**: detecta el esquema del sistema con
  `QStyleHints.colorScheme()` y aplica la paleta correspondiente (oscuro por
  defecto si no puede determinarlo). Incluye un botón para alternar el tema a
  mano (☀ / 🌙).
- Composición en **tarjetas** redondeadas con bordes sutiles, separando la zona
  de entrada (drag & drop + URL) de la de salida (visor + acciones).
- **Zona de arrastrar y soltar destacada** con borde punteado que se resalta
  con el color de acento al arrastrar un PDF encima.
- Color de acento **índigo** (`#6366f1`) consistente en el botón primario, el
  foco de los campos y la barra de progreso. Toda la paleta y el QSS se
  centralizan en `pdf2md/theme.py`.

## Arquitectura

El proyecto separa la interfaz de la lógica de negocio:

```
pdf2md/
├── __init__.py        # Metadatos del paquete
├── __main__.py        # Punto de entrada: python -m pdf2md
├── converter.py       # Lógica pura: PDF (bytes/ruta) -> Markdown
├── downloader.py      # Descarga y validación de PDF desde una URL
├── theme.py           # Paletas (claro/oscuro) y generación de QSS
└── gui.py             # Ventana PySide6 + worker en hilo
scripts/
└── smoke_test.py      # Prueba headless de la conversión (sin GUI)
assets/
├── logo.svg           # Logotipo (ícono de ventana y Dock en runtime)
└── pdf2md.icns        # Ícono del bundle macOS (PyInstaller --icon)
```

- `converter.py` y `downloader.py` **no dependen de la interfaz gráfica**, por
  lo que son fácilmente reutilizables y testeables de forma headless.

## Requisitos

- **macOS arm64** (probado), aunque el código es multiplataforma.
- **Python 3.12 o 3.14** (recomendado 3.14, con el que se verificó este
  proyecto). Vía Homebrew: `/opt/homebrew/bin/python3.14`.

### Nota sobre Python 3.14 y compatibilidad

Python 3.14 es muy reciente, pero **todas las dependencias instalan sin
problemas** porque distribuyen ruedas (`wheels`) compatibles:

- **PySide6 6.11.1** y **PyMuPDF 1.27.2.3** usan el **ABI estable de CPython**
  (`cp310-abi3`), por lo que una sola rueda sirve para 3.10+ incluido 3.14.
- **pymupdf4llm** y **httpx** son Python puro.

Si en tu sistema PySide6 no instalara en 3.14, crea el entorno con Python 3.13
o 3.12 (`/opt/homebrew/bin/python3.12`); el código es compatible con
`>=3.12`. No se requiere instalar ninguna versión adicional de Python en este
entorno, ya que 3.14 funciona correctamente.

## Instalación

Desde la raíz del proyecto (`cd pdf2md` tras clonar el repositorio):

```bash
# 1. Crear el entorno virtual con Python 3.14
/opt/homebrew/bin/python3.14 -m venv .venv

# 2. Actualizar pip e instalar dependencias dentro del venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
```

> Las dependencias se instalan **solo en `.venv`**, nunca en el Python global.

## Ejecución

```bash
# Opción recomendada (como módulo)
.venv/bin/python -m pdf2md
```

También puedes activar el entorno primero:

```bash
source .venv/bin/activate
python -m pdf2md
```

### Uso

1. Pulsa **«Abrir PDF…»** y elige un fichero, o **arrastra y suelta** un PDF
   sobre la ventana.
2. O pega una **URL** a un PDF y pulsa **«Convertir URL»**.
3. Revisa el Markdown en el visor; usa **«Guardar .md…»** o
   **«Copiar al portapapeles»**.

## Verificación headless (sin abrir la GUI)

El script `scripts/smoke_test.py` genera un PDF de ejemplo con PyMuPDF, lo
convierte a Markdown y valida el manejo de errores:

```bash
.venv/bin/python scripts/smoke_test.py
```

Para comprobar la sintaxis de todos los módulos:

```bash
.venv/bin/python -m py_compile pdf2md/*.py scripts/*.py
```

## Empaquetado y distribución (PyInstaller)

El empaquetado es **multiplataforma** y reproducible mediante el spec
versionado `pdf2md.spec`, que ramifica según el sistema operativo:

| Sistema | Salida              | Ícono              |
|---------|---------------------|--------------------|
| macOS   | `dist/pdf2md.app`   | `assets/pdf2md.icns` |
| Windows | `dist/pdf2md/` (con `pdf2md.exe`) | `assets/pdf2md.ico` |
| Linux   | `dist/pdf2md/` (con `pdf2md`)      | `assets/pdf2md.png` (vía `.desktop`) |

### Build local

Requisitos comunes en cualquier SO (dentro del `.venv` del proyecto):

```bash
pip install -r requirements.txt -r requirements-dev.txt
pyinstaller --noconfirm --clean pdf2md.spec
```

En **macOS** hay un atajo: `./scripts/build_macos.sh` (limpia `build/`+`dist/`
y ejecuta el spec). Produce `dist/pdf2md.app`.

El spec aplica, en los tres sistemas:

- **Modo onedir** (no `--onefile`): arranca más rápido. `console=False`
  equivale a `--windowed` (app GUI sin consola).
- Embebe la carpeta `assets/` (incluye `logo.svg`, que la app carga en runtime
  vía `sys._MEIPASS`). En el `.app` queda en `Contents/Resources/assets/`.
- **`collect_all("pymupdf")`** es imprescindible: arrastra los modelos de
  análisis de layout (`pymupdf/layout/resources/onnx/*.onnx`) y las
  bibliotecas nativas de MuPDF. Sin ello la conversión falla por archivos
  faltantes. También se recogen `pymupdf4llm`, `onnxruntime` y `numpy`.
- El **plugin SVG de Qt** lo recoge automáticamente el hook de PySide6, así
  que el ícono SVG carga sin flags extra.
- **Excluye** módulos pesados de Qt no usados (QtWebEngine, Qt3D,
  QtMultimedia, QtCharts, etc.) para reducir tamaño.

Tamaño aproximado: **~280 MB** (PySide6 + MuPDF + onnxruntime).

### Build en CI (GitHub Actions)

El workflow `.github/workflows/build.yml` construye los tres binarios en
paralelo con una matriz (`macos-latest`, `windows-latest`, `ubuntu-latest`),
usando **Python 3.12**. Cada job:

1. Instala dependencias (`requirements.txt` + `requirements-dev.txt`).
2. Ejecuta `pyinstaller --noconfirm --clean pdf2md.spec`.
3. Hace un **smoke test headless** del binario (`QT_QPA_PLATFORM=offscreen`)
   para detectar módulos o plugins Qt faltantes antes de publicar.
4. Sube el artefacto: `pdf2md-macos` (`.zip` del `.app`), `pdf2md-windows`
   (`.zip` de `dist/pdf2md/`) y `pdf2md-linux` (**AppImage** si se logra,
   con **fallback a `.tar.gz`**).

**Disparadores:** push de un tag `v*`, ejecución manual (`workflow_dispatch`)
y `pull_request` (solo validación de build, sin publicar release). Cuando se
empuja un tag `v*`, un job final crea un **GitHub Release** adjuntando los tres
artefactos.

### Descargar los binarios

- Desde la pestaña **Actions** del repositorio: abre la ejecución del workflow
  y descarga los artefactos `pdf2md-macos` / `pdf2md-windows` / `pdf2md-linux`.
- O desde la pestaña **Releases** (si se publicó un tag `v*`).

### Binarios sin firmar

Los binarios **no están firmados ni notarizados**:

- **macOS (Gatekeeper):** en el primer arranque, clic derecho sobre
  `pdf2md.app` → **"Abrir"** y confirmar; o ejecutar
  `xattr -dr com.apple.quarantine pdf2md.app`.
- **Windows (SmartScreen):** puede aparecer "Windows protegió tu PC"; pulsa
  **"Más información" → "Ejecutar de todas formas"**.
- **Linux (AppImage):** dale permiso de ejecución
  (`chmod +x pdf2md-*.AppImage`) y ejecútalo; el `.tar.gz` se descomprime y se
  lanza `./pdf2md/pdf2md`.

## Repositorio y publicación

Este proyecto se versiona con git. Para crear el repositorio en GitHub y
disparar el primer build multiplataforma:

```bash
# 1. Crear el repo remoto (requiere gh autenticado) y empujar main
gh repo create pdf2md --public --source=. --remote=origin --push

# (alternativa manual sin gh)
# git remote add origin git@github.com:<usuario>/pdf2md.git
# git push -u origin main

# 2. Disparar el primer build + release etiquetando una versión
git tag v0.1.0
git push origin v0.1.0
```

El push del tag `v0.1.0` activa el workflow, que construye los tres binarios y
publica el Release con los artefactos adjuntos.

## Licencia

MIT.
