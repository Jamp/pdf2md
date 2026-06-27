#!/usr/bin/env bash
#
# Empaqueta pdf2md como bundle .app de macOS usando PyInstaller.
#
# Requisitos:
#   - macOS (arm64 o x86_64).
#   - virtualenv del proyecto en .venv con las dependencias instaladas:
#       .venv/bin/pip install -r requirements.txt
#       .venv/bin/pip install -r requirements-dev.txt
#
# Uso:
#   ./scripts/build_macos.sh
#
# Resultado: dist/pdf2md.app
set -euo pipefail

# Raíz del proyecto (un nivel por encima de scripts/).
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PYINSTALLER="$ROOT_DIR/.venv/bin/pyinstaller"

if [[ ! -x "$PYINSTALLER" ]]; then
    echo "ERROR: no se encontró PyInstaller en .venv." >&2
    echo "Instálalo con: .venv/bin/pip install -r requirements-dev.txt" >&2
    exit 1
fi

echo "==> Limpiando builds anteriores..."
rm -rf build dist

echo "==> Generando bundle con PyInstaller..."
"$PYINSTALLER" --noconfirm --clean pdf2md.spec

echo "==> Build completado: dist/pdf2md.app"
du -sh dist/pdf2md.app
