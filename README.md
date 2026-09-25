# Mail Organizer

Intelligente E-Mail-Verwaltung mit lokaler LLM-Integration ([Ollama](https://ollama.com)).
Umsetzung von Phase 1 (Basis) und Phase 2 (Ollama-Integration) aus [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md).

## Features

- IMAP/SMTP-Anbindung (Abrufen, Senden, Flaggen, Verschieben/Löschen von Mails)
- Lokale Analyse von Mails über Ollama (Kategorie, Wichtigkeit, Sentiment, empfohlene Aktion)
- SQLite-Persistierung via SQLAlchemy (Mails, Analyse-Ergebnisse, Einstellungen)
- PyQt6-GUI mit Mail-Liste, Vorschau-Panel und Analyse-Anzeige
- Verschlüsselte Passwort-Speicherung (`cryptography.fernet`)
- Automatischer Hintergrund-Sync (konfigurierbares Intervall)

## Installation

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Für Ollama-Analyse wird ein laufender lokaler Ollama-Server benötigt: https://ollama.com

## Konfiguration

Kopiere `.env.example` nach `.env` und passe die Werte an. Für verschlüsselte Passwort-Speicherung
einen Master-Key generieren:

```bash
python -c "from mailorganizer.utils.crypto import generate_master_key; print(generate_master_key())"
```

und als `MAILORGANIZER_MASTER_KEY` in der `.env` hinterlegen.

## Ausführen

```bash
python -m mailorganizer.main
```

Beim ersten Start öffnet sich der Einstellungs-Dialog zur Konfiguration von Mail-Konto und Ollama.

## Tests

```bash
pip install -r requirements-dev.txt
pytest
```

## Projektstruktur

Siehe Abschnitt 3.1 in [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) für die vollständige
Zielarchitektur. Aktuell umgesetzt:

- `mailorganizer/config` – Einstellungen & Konstanten
- `mailorganizer/models` – SQLAlchemy-ORM-Modelle & Datenklassen
- `mailorganizer/services` – Mail-, Ollama-, Analyse-, Storage- und Scheduler-Service
- `mailorganizer/ui` – PyQt6-Hauptfenster, Widgets, Dark/Light-Themes
- `mailorganizer/utils` – Logging, Exceptions, Validierung, Krypto-Helfer, Mail-Utils
- `tests` – Unit-Tests für Mail-, Ollama- und Analyse-Service

## Offene Punkte (nächste Phasen)

Gemäß Roadmap in IMPLEMENTATION_PLAN.md sind Phase 3–5 (benutzerdefinierte Analyse-Regeln-UI,
Batch-Processing, Reporting/Charts, Model-Benchmarking, externe Integrationen) noch nicht
umgesetzt und können iterativ auf dieser Basis aufgebaut werden.
