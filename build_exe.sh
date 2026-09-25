#!/usr/bin/env bash
# Builds a standalone Mail Organizer binary for the current OS (Linux/macOS) via
# PyInstaller. Result: dist/MailOrganizer/MailOrganizer (plus its dependency
# files in the same folder — ship the whole dist/MailOrganizer directory).
#
# Uses its own virtual environment (.venv-build) so PyInstaller only picks up
# what the app actually needs, not test/dev dependencies.
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"

PYTHON_BIN="${PYTHON_BIN:-python3}"

echo "== Mail Organizer: Build =="

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
    echo "Fehler: $PYTHON_BIN wurde nicht gefunden. Bitte Python 3.11+ installieren."
    exit 1
fi

if [ ! -d ".venv-build" ]; then
    echo "Erstelle Build-Umgebung (.venv-build) ..."
    "$PYTHON_BIN" -m venv .venv-build
fi

VENV_PY=".venv-build/bin/python"
VENV_PIP=".venv-build/bin/pip"

echo "Installiere Abhaengigkeiten (inkl. PyInstaller) ..."
"$VENV_PIP" install --upgrade pip >/dev/null
"$VENV_PIP" install --no-cache-dir -r requirements-build.txt

echo ""
echo "Baue MailOrganizer ..."
rm -rf build dist
"$VENV_PY" -m PyInstaller mailorganizer.spec --noconfirm

echo ""
echo "== Fertig =="
echo "Die App liegt in:  dist/MailOrganizer/"
echo "Starten mit:       dist/MailOrganizer/MailOrganizer"
echo ""
echo "Wichtig: den kompletten Ordner dist/MailOrganizer weitergeben/kopieren,"
echo "nicht nur die Binary allein - die Abhaengigkeiten daneben werden gebraucht."
