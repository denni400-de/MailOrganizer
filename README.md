# Mail Organizer

Intelligente E-Mail-Verwaltung mit lokaler LLM-Integration ([Ollama](https://ollama.com)).
Umsetzung von Phase 1–3 (Basis, Ollama-Integration, Intelligente Features) aus
[IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md).

## Features

- IMAP/SMTP-Anbindung (Abrufen, Senden, Flaggen, Verschieben/Löschen von Mails)
- Lokale Analyse von Mails über Ollama (Kategorie, Wichtigkeit, Sentiment, empfohlene Aktion)
- SQLite-Persistierung via SQLAlchemy (Mails, Analyse-Ergebnisse, Einstellungen, Regeln)
- PyQt6-GUI mit Mail-Liste, Vorschau-Panel und Analyse-Anzeige
- Verschlüsselte Passwort-Speicherung (`cryptography.fernet`)
- Automatischer Hintergrund-Sync (konfigurierbares Intervall)
- **Benutzerdefinierte Analyse-Regeln** (Tab "Analyse-Regeln"): Bedingung (Feld/Operator/Wert)
  → Aktion (archivieren, löschen, flaggen, Kategorie setzen), mit Priorität und Aktiv-Schalter.
  Regeln werden nach jeder Analyse automatisch angewendet (erste passende Regel gewinnt).
- **Mail-Cleanup** (🗑️-Button): alte Mails archivieren (älter als X Tage), Spam löschen,
  Duplikate entfernen, optional Liste danach nach Wichtigkeit sortiert anzeigen —
  mit Bestätigung, Fortschrittsanzeige und Zusammenfassung.
- **Batch-Aktion**: Rechtsklick auf eine Mail → "Alle Mails von diesem Sender archivieren"

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
- `mailorganizer/services` – Mail-, Ollama-, Analyse-, Storage-, Scheduler-, Regel- und Cleanup-Service
- `mailorganizer/ui` – PyQt6-Hauptfenster, Widgets (inkl. Analyse-Regeln-Tab, Cleanup-Dialog), Dark/Light-Themes
- `mailorganizer/utils` – Logging, Exceptions, Validierung, Krypto-Helfer, Mail-Utils
- `tests` – Unit-Tests für Mail-, Ollama-, Analyse-, Regel- und Cleanup-Service

### Analyse-Regeln: Bedingungsformat

Jede Regel hat genau eine Bedingung, gespeichert als JSON in `analysis_rules.condition`:

```json
{"field": "sender", "operator": "contains", "value": "amazon", "set_category": "shopping"}
```

- `field`: `sender` | `subject` | `category` | `importance_score` | `sentiment` | `keywords`
- `operator`: `contains` | `equals` | `gt` | `lt` | `gte` | `lte`
- `set_category`: nur relevant, wenn `action == "category"`

## Offene Punkte (nächste Phasen)

Gemäß Roadmap in IMPLEMENTATION_PLAN.md sind Phase 4–5 (Reporting/Charts mit PDF-Export,
Ollama-Model-Benchmarking, externe Integrationen wie Slack/Discord/Webhooks, Spracherkennung)
noch nicht umgesetzt und können iterativ auf dieser Basis aufgebaut werden.
