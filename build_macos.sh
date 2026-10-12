#!/bin/bash
set -euo pipefail

cd "$(dirname "$0")"

VENV_DIR=".venv-mac"
if [[ ! -x "$VENV_DIR/bin/python" ]]; then
    python3 -m venv "$VENV_DIR"
fi

source "$VENV_DIR/bin/activate"
python -m pip install --upgrade pip
python -m pip install -e '.[dev,build]'
python -m pytest
python -m PyInstaller --noconfirm --clean packaging/fastapi_service_macos.spec

codesign --force --deep --sign - dist/FastAPI-Service.app
"$PWD/verify_macos.sh"

ARCHITECTURE="$(uname -m)"
ARCHIVE="dist/FastAPI-Service-macos-${ARCHITECTURE}.zip"
rm -f "$ARCHIVE"
ditto -c -k --sequesterRsrc --keepParent dist/FastAPI-Service.app "$ARCHIVE"

echo
echo "Build completed: $ARCHIVE"
echo "Copy this ZIP to a Mac with the same CPU architecture for testing."
