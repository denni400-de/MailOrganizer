# Mail Organizer

Intelligente E-Mail-Verwaltung mit lokaler LLM-Integration ([Ollama](https://ollama.com)).
Umsetzung von Phase 1–5 (Basis, Ollama-Integration, Intelligente Features, UX & Polish,
Advanced) aus [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md).

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
- **Wöchentlicher Bericht** (📊-Button): Top-Absender, Kategorie-Statistik (Kreisdiagramm),
  Wichtigkeits-Verteilung (Balkendiagramm), Aufräum-Vorschläge — mit PDF-Export (über Qt's
  eingebauten `QPdfWriter`, ohne zusätzliche Abhängigkeit).
- **Ollama-Model-Benchmarking** (🏁-Button): dieselben Mails mit mehreren Modellen analysieren
  und Trefferzahl/Fehler/Ø-Zeit vergleichen.
- **Externe Integrationen** (Tab "Integrationen"): Webhook-Benachrichtigung (Generic/Slack/Discord-Format)
  bei Mails ab einer konfigurierbaren Wichtigkeits-Schwelle, inkl. Test-Button.
- **Mehrsprachige Analyse**: automatische Spracherkennung (heuristisch, ohne zusätzliche
  Abhängigkeit) oder feste Sprache für die Analyse-Prompts, einstellbar in "UI-Einstellungen".
- **UI-Einstellungen**: Dark/Light-Theme (sofort angewendet), Schriftgröße, Analyse-Sprache —
  persistiert pro Benutzer.

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
- `mailorganizer/services` – Mail-, Ollama-, Analyse-, Storage-, Scheduler-, Regel-, Cleanup-,
  Report-, Benchmark-, Webhook- und Sprach-Service
- `mailorganizer/ui` – PyQt6-Hauptfenster, Widgets (Analyse-Regeln, Cleanup, Bericht, Benchmark,
  Integrationen, UI-Einstellungen), eigene QPainter-Chart-Widgets (Pie/Bar, ohne matplotlib),
  Dark/Light-Themes
- `mailorganizer/utils` – Logging, Exceptions, Validierung, Krypto-Helfer, Mail-Utils
- `tests` – Unit-Tests für alle Services (60 Tests)

### Analyse-Regeln: Bedingungsformat

Jede Regel hat genau eine Bedingung, gespeichert als JSON in `analysis_rules.condition`:

```json
{"field": "sender", "operator": "contains", "value": "amazon", "set_category": "shopping"}
```

- `field`: `sender` | `subject` | `category` | `importance_score` | `sentiment` | `keywords`
- `operator`: `contains` | `equals` | `gt` | `lt` | `gte` | `lte`
- `set_category`: nur relevant, wenn `action == "category"`

## Design-Entscheidungen

Gemäß Plan-Abschnitt 16 ("Dependencies Minimieren") wurden Charts und PDF-Export bewusst ohne
neue Abhängigkeiten umgesetzt: die Kreis-/Balkendiagramme sind selbst geschriebene
QPainter-Widgets (`ui/widgets/charts.py`), der PDF-Export nutzt Qt's eingebauten `QPdfWriter`,
und die Spracherkennung ist eine leichte Stopword-Heuristik statt einer ML-Bibliothek.
Alle bisherigen Requirements (`requirements.txt`) sind unverändert ausreichend.

## Offene Punkte (nächste Phasen)

Nicht umgesetzt (aus Plan-Abschnitt 8.5/13): Mobile-Companion-App (eigenständiges,
plattformübergreifendes Projekt außerhalb dieses Repos), ein programmatischer REST-API-Endpunkt
für externe Automatisierung (das Webhook-Feature deckt den "Mail Organizer → extern"-Weg bereits
ab), sowie Alembic-Migrationen (aktuell reicht `create_all` für das MVP-Schema).
