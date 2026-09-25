@echo off
REM Baut eine eigenstaendige Windows-.exe von Mail Organizer via PyInstaller.
REM Ergebnis: dist\MailOrganizer\MailOrganizer.exe (samt aller benoetigten DLLs
REM im selben Ordner - diesen kompletten Ordner weitergeben/kopieren, nicht
REM nur die .exe alleine).
REM
REM Nutzt bewusst eine eigene virtuelle Umgebung (.venv-build) statt der
REM normalen .venv, damit PyInstaller nur das einsammelt, was die App
REM tatsaechlich braucht, und keine Dev-/Test-Abhaengigkeiten mit einpackt.

setlocal enabledelayedexpansion
cd /d "%~dp0"

echo ================================
echo  Mail Organizer - .exe bauen
echo ================================
echo.

REM -- Windows "Long Path"-Unterstuetzung pruefen ---------------------------
REM Gleicher Hintergrund wie in start.bat: PyInstaller sammelt alle PyQt6-Dateien
REM ein (inkl. tief verschachtelter Qt6-QML-Dateien); ohne Long-Path-Unterstuetzung
REM kann das Einsammeln an einem langen Projektpfad genauso fehlschlagen wie die
REM normale Installation.
set "LONGPATHS_VALUE="
for /f "tokens=3" %%V in ('reg query "HKLM\SYSTEM\CurrentControlSet\Control\FileSystem" /v LongPathsEnabled 2^>nul ^| findstr /i LongPathsEnabled') do set "LONGPATHS_VALUE=%%V"
if not "!LONGPATHS_VALUE!"=="0x1" (
    echo Warnung: Windows "Long Path"-Unterstuetzung ist nicht aktiviert.
    echo Falls der Build gleich fehlschlaegt: start.bat einmal ausfuehren
    echo ^(aktiviert Long Paths automatisch^), oder den Projektordner an
    echo einen kurzen Pfad verschieben, z.B. nach C:\MailOrganizer.
    echo.
)

REM -- Python finden ------------------------------------------------------
set "PYTHON_LAUNCHER="
where py >nul 2>&1
if %errorlevel%==0 (
    set "PYTHON_LAUNCHER=py"
) else (
    where python >nul 2>&1
    if !errorlevel!==0 (
        set "PYTHON_LAUNCHER=python"
    ) else (
        echo Fehler: Python wurde nicht gefunden.
        echo Bitte Python 3.11+ installieren: https://www.python.org/downloads/
        goto :error
    )
)

REM -- Eigene Build-Umgebung anlegen ----------------------------------------
if not exist ".venv-build\Scripts\python.exe" (
    echo Erstelle Build-Umgebung ^(.venv-build^) ...
    %PYTHON_LAUNCHER% -m venv .venv-build
    if not exist ".venv-build\Scripts\python.exe" (
        echo Fehler: Build-Umgebung konnte nicht erstellt werden.
        goto :error
    )
)

set "VENV_PY=.venv-build\Scripts\python.exe"
set "VENV_PIP=.venv-build\Scripts\pip.exe"

echo Installiere Abhaengigkeiten ^(inkl. PyInstaller^) ...
"%VENV_PIP%" install --upgrade pip >nul
"%VENV_PIP%" install --no-cache-dir -r requirements-build.txt
if not %errorlevel%==0 (
    echo Fehler: Abhaengigkeiten konnten nicht installiert werden.
    goto :error
)

echo.
echo Baue MailOrganizer.exe ...
echo.
if exist "build" rmdir /s /q "build"
if exist "dist" rmdir /s /q "dist"
"%VENV_PY%" -m PyInstaller mailorganizer.spec --noconfirm
if not %errorlevel%==0 (
    echo.
    echo Fehler: Build fehlgeschlagen.
    goto :error
)

echo.
echo ================================
echo  Fertig!
echo ================================
echo Die App liegt in:  dist\MailOrganizer\
echo Starten mit:       dist\MailOrganizer\MailOrganizer.exe
echo.
echo Wichtig: den KOMPLETTEN Ordner "dist\MailOrganizer" weitergeben/kopieren,
echo nicht nur die .exe-Datei allein - die DLLs daneben werden gebraucht.
echo.
pause
exit /b 0

:error
echo.
pause
exit /b 1
