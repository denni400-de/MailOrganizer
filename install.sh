#!/usr/bin/env bash
# Mail Organizer – Installationsskript für Linux/macOS.
# Legt eine virtuelle Umgebung an, installiert alle Abhängigkeiten,
# erzeugt eine .env mit generiertem Verschlüsselungs-Key und zeigt an,
# wie die App gestartet wird.
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"

PYTHON_BIN="${PYTHON_BIN:-python3}"

echo "== Mail Organizer Installation =="

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
    echo "Fehler: $PYTHON_BIN wurde nicht gefunden. Bitte Python 3.11+ installieren: https://www.python.org/downloads/"
    exit 1
fi

PY_VERSION="$("$PYTHON_BIN" -c 'import sys; print("%d.%d" % sys.version_info[:2])')"
echo "Gefundene Python-Version: $PY_VERSION"

if [ ! -d ".venv" ]; then
    echo "Erstelle virtuelle Umgebung (.venv) ..."
    "$PYTHON_BIN" -m venv .venv
else
    echo "Virtuelle Umgebung (.venv) existiert bereits, überspringe."
fi

VENV_PY=".venv/bin/python"
VENV_PIP=".venv/bin/pip"

echo "Installiere Abhängigkeiten ..."
"$VENV_PIP" install --upgrade pip >/dev/null
"$VENV_PIP" install -r requirements.txt

if [ ! -f ".env" ]; then
    echo "Erstelle .env aus .env.example ..."
    cp .env.example .env

    echo "Generiere Verschlüsselungs-Schlüssel für gespeicherte Passwörter ..."
    MASTER_KEY="$("$VENV_PY" -c 'from mailorganizer.utils.crypto import generate_master_key; print(generate_master_key())')"

    # Portabler sed-Aufruf für macOS (BSD sed) und Linux (GNU sed)
    if sed --version >/dev/null 2>&1; then
        sed -i "s|^MAILORGANIZER_MASTER_KEY=.*|MAILORGANIZER_MASTER_KEY=${MASTER_KEY}|" .env
    else
        sed -i '' "s|^MAILORGANIZER_MASTER_KEY=.*|MAILORGANIZER_MASTER_KEY=${MASTER_KEY}|" .env
    fi
    echo "Schlüssel in .env eingetragen."
else
    echo ".env existiert bereits, überspringe (kein Schlüssel überschrieben)."
fi

echo ""
echo "== Installation abgeschlossen =="
echo ""
echo "Voraussetzung für die KI-Analyse: ein laufender lokaler Ollama-Server (https://ollama.com)."
echo ""
echo "App starten mit:"
echo "  .venv/bin/python -m mailorganizer.main"
echo ""
echo "Oder Umgebung aktivieren und dann starten:"
echo "  source .venv/bin/activate"
echo "  python -m mailorganizer.main"
