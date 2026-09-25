@echo off
REM Mail Organizer - robuster Windows-Start.
REM Prueft bei jedem Start, ob die virtuelle Umgebung und PyQt6 wirklich funktionieren,
REM repariert sie bei Bedarf automatisch (haeufige Ursache: PyQt6 wurde unvollstaendig
REM installiert, z.B. durch Antivirus-Eingriff waehrend der Installation) und startet dann
REM die App. Das Fenster bleibt bei einem Fehler offen, damit die Meldung lesbar bleibt.

setlocal enabledelayedexpansion
cd /d "%~dp0"

echo ================================
echo  Mail Organizer - Start
echo ================================
echo.

REM -- Windows "Long Path"-Unterstuetzung pruefen/aktivieren ---------------
REM PyQt6 enthaelt sehr tief verschachtelte Qt6-QML-Dateien. Kombiniert mit
REM einem langen Projektpfad (z.B. verschachtelte Download-Ordner) ueberschreitet
REM der volle Pfad leicht Windows' klassisches 260-Zeichen-Limit, und die
REM Installation bricht mit "No such file or directory" ab - das aeussert sich
REM spaeter als "ModuleNotFoundError: No module named 'PyQt6.QtWidgets'", weil
REM nur ein Teil der Pakete tatsaechlich geschrieben wurde.
set "LONGPATHS_VALUE="
for /f "tokens=3" %%V in ('reg query "HKLM\SYSTEM\CurrentControlSet\Control\FileSystem" /v LongPathsEnabled 2^>nul ^| findstr /i LongPathsEnabled') do set "LONGPATHS_VALUE=%%V"

if not "!LONGPATHS_VALUE!"=="0x1" (
    echo Windows "Long Path"-Unterstuetzung ist nicht aktiviert - das fuehrt bei
    echo PyQt6 haeufig zu abgebrochenen Installationen. Versuche sie zu aktivieren
    echo ^(erfordert Administratorrechte^) ...
    reg add "HKLM\SYSTEM\CurrentControlSet\Control\FileSystem" /v LongPathsEnabled /t REG_DWORD /d 1 /f >nul 2>&1
    if not !errorlevel!==0 (
        echo Keine Administratorrechte in diesem Fenster - oeffne Bestaetigungsdialog ...
        powershell -NoProfile -Command "Start-Process reg -ArgumentList 'add','HKLM\SYSTEM\CurrentControlSet\Control\FileSystem','/v','LongPathsEnabled','/t','REG_DWORD','/d','1','/f' -Verb RunAs -Wait" >nul 2>&1
    )
    set "LONGPATHS_VALUE="
    for /f "tokens=3" %%V in ('reg query "HKLM\SYSTEM\CurrentControlSet\Control\FileSystem" /v LongPathsEnabled 2^>nul ^| findstr /i LongPathsEnabled') do set "LONGPATHS_VALUE=%%V"
    if "!LONGPATHS_VALUE!"=="0x1" (
        echo Long Paths aktiviert.
    ) else (
        echo.
        echo Long Paths konnten nicht aktiviert werden ^(Dialog abgebrochen oder
        echo keine Administratorrechte verfuegbar^). Falls die Installation gleich
        echo fehlschlaegt: entweder als Administrator erneut versuchen, oder den
        echo Projektordner an einen kurzen Pfad verschieben, z.B. nach C:\MailOrganizer
        echo ^(der aktuelle Pfad ist sehr lang^).
    )
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
        echo Wichtig beim Installer: Haekchen bei "Add python.exe to PATH" setzen.
        goto :error
    )
)

REM -- Virtuelle Umgebung anlegen, falls sie fehlt -------------------------
if not exist ".venv\Scripts\python.exe" (
    echo Erstelle virtuelle Umgebung ^(.venv^) ...
    %PYTHON_LAUNCHER% -m venv .venv
    if not exist ".venv\Scripts\python.exe" (
        echo Fehler: Virtuelle Umgebung konnte nicht erstellt werden.
        goto :error
    )
)

set "VENV_PY=.venv\Scripts\python.exe"
set "VENV_PIP=.venv\Scripts\pip.exe"

REM -- Pruefen, ob PyQt6 (insbesondere QtWidgets) wirklich funktioniert ----
"%VENV_PY%" -c "from PyQt6.QtWidgets import QApplication" >nul 2>&1
if not %errorlevel%==0 (
    echo PyQt6 ist nicht ^(vollstaendig^) installiert - installiere neu ...
    echo ^(Das behebt u.a. den Fehler "ModuleNotFoundError: No module named 'PyQt6.QtWidgets'"^)
    "%VENV_PIP%" uninstall -y PyQt6 PyQt6-Qt6 PyQt6-sip >nul 2>&1
    "%VENV_PIP%" install --upgrade pip >nul
    "%VENV_PIP%" install --no-cache-dir -r requirements.txt
    if not exist ".venv\Scripts\python.exe" (
        goto :error
    )
    "%VENV_PY%" -c "from PyQt6.QtWidgets import QApplication" >nul 2>&1
    if not !errorlevel!==0 (
        echo.
        echo Fehler: PyQt6 laesst sich weiterhin nicht laden.
        echo Wahrscheinlichste Ursache: der Projektpfad ist zu lang
        echo ^(PyQt6 enthaelt sehr tief verschachtelte Dateien unter Qt6\qml\...^).
        echo Falls oben eine Meldung wie "No such file or directory" oder
        echo "Long Path" auftauchte: entweder als Administrator erneut starten
        echo ^(damit Long Paths automatisch aktiviert werden koennen^), oder den
        echo Projektordner an einen kurzen Pfad verschieben, z.B. C:\MailOrganizer.
        echo.
        echo Weitere moegliche Ursachen:
        echo  - Antivirus/Windows Defender blockiert Dateien in .venv\Lib\site-packages\PyQt6
        echo  - Ein Conda/Anaconda-Prompt ueberschreibt PYTHONPATH im Hintergrund
        echo.
        echo Pruefe zur Diagnose:  dir .venv\Lib\site-packages\PyQt6
        goto :error
    )
    echo PyQt6 erfolgreich repariert.
) else (
    REM Restliche Abhaengigkeiten still auf dem neuesten Stand halten.
    "%VENV_PIP%" install -q -r requirements.txt
)

REM -- .env anlegen, falls sie fehlt ---------------------------------------
if not exist ".env" (
    if exist ".env.example" (
        echo Erstelle .env aus .env.example ...
        copy /y ".env.example" ".env" >nul
        for /f "delims=" %%K in ('"%VENV_PY%" -c "from mailorganizer.utils.crypto import generate_master_key; print(generate_master_key())"') do set "MAILORGANIZER_NEW_KEY=%%K"
        REM Der Schluessel wird ueber die Umgebungsvariable an Python uebergeben statt
        REM direkt in den Quellcode eingebettet - so gibt es keine Probleme mit
        REM Sonderzeichen oder Batch-Escaping.
        if defined MAILORGANIZER_NEW_KEY (
            "%VENV_PY%" -c "import os, re; p = '.env'; s = open(p, encoding='utf-8').read(); s = re.sub(r'(?m)^MAILORGANIZER_MASTER_KEY=.*$', 'MAILORGANIZER_MASTER_KEY=' + os.environ['MAILORGANIZER_NEW_KEY'], s); open(p, 'w', encoding='utf-8').write(s)"
        )
    )
)

echo.
echo Starte Mail Organizer ...
echo.
"%VENV_PY%" -m mailorganizer.main
set "APP_EXIT_CODE=%errorlevel%"

if not %APP_EXIT_CODE%==0 (
    echo.
    echo Die App wurde mit Fehlercode %APP_EXIT_CODE% beendet.
    goto :error
)

exit /b 0

:error
echo.
echo ================================
echo  Beendet mit Fehler.
echo ================================
pause
exit /b 1
