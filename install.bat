@echo off
REM Mail Organizer - Doppelklick-Installer fuer Windows.
REM Ruft install.ps1 mit gelockerter ExecutionPolicy auf, damit kein manuelles
REM Anpassen der PowerShell-Sicherheitsrichtlinie noetig ist.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1"
pause
