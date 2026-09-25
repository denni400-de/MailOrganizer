# Mail Organizer - Installationsskript fuer Windows (PowerShell).
# Legt eine virtuelle Umgebung an, installiert alle Abhaengigkeiten,
# erzeugt eine .env mit generiertem Verschluesselungs-Key.
#
# Ausfuehren mit:
#   powershell -ExecutionPolicy Bypass -File install.ps1
# oder in einer PowerShell mit bereits gelockerter ExecutionPolicy einfach:
#   .\install.ps1

$ErrorActionPreference = "Stop"

Set-Location -Path $PSScriptRoot

Write-Host "== Mail Organizer Installation =="

$pythonCmd = Get-Command python -ErrorAction SilentlyContinue
if (-not $pythonCmd) {
    $pythonCmd = Get-Command py -ErrorAction SilentlyContinue
}
if (-not $pythonCmd) {
    Write-Host "Fehler: Python wurde nicht gefunden. Bitte Python 3.11+ installieren: https://www.python.org/downloads/"
    exit 1
}
$pythonExe = $pythonCmd.Source
Write-Host "Gefundenes Python: $pythonExe"

if (-not (Test-Path ".venv")) {
    Write-Host "Erstelle virtuelle Umgebung (.venv) ..."
    & $pythonExe -m venv .venv
} else {
    Write-Host "Virtuelle Umgebung (.venv) existiert bereits, ueberspringe."
}

$venvPython = ".venv\Scripts\python.exe"
$venvPip = ".venv\Scripts\pip.exe"

Write-Host "Installiere Abhaengigkeiten ..."
& $venvPip install --upgrade pip | Out-Null
& $venvPip install -r requirements.txt

if (-not (Test-Path ".env")) {
    Write-Host "Erstelle .env aus .env.example ..."
    Copy-Item ".env.example" ".env"

    Write-Host "Generiere Verschluesselungs-Schluessel fuer gespeicherte Passwoerter ..."
    $masterKey = & $venvPython -c "from mailorganizer.utils.crypto import generate_master_key; print(generate_master_key())"

    (Get-Content ".env") -replace '^MAILORGANIZER_MASTER_KEY=.*', "MAILORGANIZER_MASTER_KEY=$masterKey" |
        Set-Content ".env"
    Write-Host "Schluessel in .env eingetragen."
} else {
    Write-Host ".env existiert bereits, ueberspringe (kein Schluessel ueberschrieben)."
}

Write-Host ""
Write-Host "== Installation abgeschlossen =="
Write-Host ""
Write-Host "Voraussetzung fuer die KI-Analyse: ein laufender lokaler Ollama-Server (https://ollama.com)."
Write-Host ""
Write-Host "App starten mit:"
Write-Host "  .venv\Scripts\python.exe -m mailorganizer.main"
Write-Host ""
Write-Host "Oder Umgebung aktivieren und dann starten:"
Write-Host "  .venv\Scripts\Activate.ps1"
Write-Host "  python -m mailorganizer.main"
