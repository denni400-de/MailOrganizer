"""First-run welcome: explains the 3-step setup and takes the user straight to the
Einstellungen tab, instead of silently dropping them there with no context.
"""

from __future__ import annotations

from PyQt6.QtWidgets import QMessageBox


def maybe_show_welcome(parent, has_account: bool) -> None:
    """Show a one-time welcome dialog and switch to Einstellungen if no account exists yet."""
    if has_account:
        return

    box = QMessageBox(parent)
    box.setWindowTitle("Willkommen bei Mail Organizer")
    box.setIcon(QMessageBox.Icon.Information)
    box.setText("Bevor es losgeht, richte kurz dein Mail-Konto ein.")
    box.setInformativeText(
        "In drei Schritten:\n\n"
        "1. Mail-Einstellungen: IMAP-/SMTP-Server, E-Mail-Adresse und Passwort eintragen.\n"
        "   Mit „Verbindungs-Test“ prüfen, ob es klappt.\n\n"
        "2. Ollama-Konfiguration: die Adresse deines lokalen Ollama-Servers "
        "(Standard: http://localhost:11434) und ein Modell auswählen.\n\n"
        "3. Unten auf „Speichern“ klicken — danach synchronisiert die App automatisch "
        "dein Postfach.\n\n"
        "Die weiteren Reiter (Analyse-Regeln, Integrationen, UI) sind optional und "
        "können jederzeit später angepasst werden."
    )
    box.setStandardButtons(QMessageBox.StandardButton.Ok)
    box.exec()
