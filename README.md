# Mail Organizer

Intelligente E-Mail-Verwaltung mit lokaler LLM-Integration ([Ollama](https://ollama.com)).
Umsetzung von Phase 1–5 (Basis, Ollama-Integration, Intelligente Features, UX & Polish,
Advanced) aus [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md).

## Oberfläche

Ein Fenster, ein Tab pro Funktionsbereich (kein Popup-Wirrwarr, nichts wird abgeschnitten):

- **📬 Postfach** – Ordner-Baum links im Outlook-Stil (auf-/zuklappbar, aus IMAP oder bereits
  synchronisierten Ordnern, verschachtelte Ordner wie „INBOX/Archiv/2024“ werden korrekt
  eingerückt statt flach aufgelistet), Mail-Liste, Vorschau mit Analyse-Ergebnis. Rechtsklick auf
  eine Mail → "Alle Mails von diesem Sender archivieren".
- **📊 Bericht** – Top-Absender, Kategorie-Statistik (Kreisdiagramm), Wichtigkeits-Verteilung
  (Balkendiagramm), Aufräum-Vorschläge. Füllt den verfügbaren Platz (Scroll-Bereich, kein Abschneiden),
  PDF-Export über Qt's eingebauten `QPdfWriter` (keine zusätzliche Abhängigkeit).
- **🗑️ Cleanup** – zeigt vor jeder Aktion genau, welche Mails betroffen wären (alte Mails,
  Spam, Duplikate), einzeln an-/abwählbar. Erst nach expliziter Auswahl + Bestätigung wird etwas
  archiviert/gelöscht — keine blinde "unwiderruflich löschen?"-Frage mehr.
- **🏁 Benchmark** – dieselben Mails mit mehreren Ollama-Modellen analysieren, Trefferzahl/
  Fehler/Ø-Zeit vergleichen.
- **💬 Chat** – Konversation mit der KI, die per Tool-Calling im Postfach suchen, Mails
  zusammenfassen oder auf Zuruf archivieren kann (z. B. "Zeig mir alle Rechnungen von dieser
  Woche" oder "Archiviere die Werbemails von Amazon"). Tool-Aufrufe werden transparent im
  Verlauf angezeigt (kursiv); Treffer aus `list_mails`/`search_mails` erscheinen zusätzlich als
  anklickbare Tabelle mit Volltext-Vorschau rechts neben dem Chatverlauf.
- **⚙️ Einstellungen** – Mail-Konto, Ollama, Analyse-Regeln, Integrationen, UI (Theme/Schriftgröße/
  Sprache) als Unterreiter, mit explizitem Speichern-Button. Solange noch kein Konto eingerichtet
  ist, erklärt ein Hinweis-Banner die nötigen Schritte; beim allerersten Start führt zusätzlich ein
  Willkommens-Dialog kurz durch die Einrichtung.

Eine schlanke Toolbar (🔄 Sync, 🧠 Analysieren, 📁 Ordner laden) bleibt immer sichtbar, da diese
Aktionen unabhängig vom gerade offenen Tab gebraucht werden.

### Reaktionsfähigkeit

Alle netzwerk-/KI-lastigen Operationen (IMAP-Sync, Ordner laden, Analyse, Chat, Benchmark,
Verbindungstests in den Einstellungen) laufen auf einem Hintergrund-Thread
(`ui/workers.py`, `QThreadPool`-basiert) statt den GUI-Thread zu blockieren. Während einer
Operation zeigt die Statusleiste einen Fortschrittsbalken mit Beschreibung
("Synchronisiere „INBOX“ …" etc.) und die betroffenen Buttons werden deaktiviert, damit die
App nie eingefroren wirkt und keine doppelten Aktionen ausgelöst werden können.

## Weitere Features

- Lokale Analyse von Mails über Ollama (Kategorie, Wichtigkeit, Sentiment, empfohlene Aktion)
- SQLite-Persistierung via SQLAlchemy (Mails inkl. Ordner, Analyse-Ergebnisse, Einstellungen, Regeln)
  — bestehende Datenbanken werden beim Start automatisch migriert (z. B. neue `folder`-Spalte)
- Verschlüsselte Passwort-Speicherung (`cryptography.fernet`)
- Automatischer Hintergrund-Sync (konfigurierbares Intervall)
- **Benutzerdefinierte Analyse-Regeln**: Bedingung (Feld/Operator/Wert) → Aktion (archivieren,
  löschen, flaggen, Kategorie setzen), mit Priorität und Aktiv-Schalter. Regeln werden nach jeder
  Analyse automatisch angewendet (erste passende Regel gewinnt).
- **Externe Integrationen**: Webhook-Benachrichtigung (Generic/Slack/Discord-Format) bei Mails ab
  einer konfigurierbaren Wichtigkeits-Schwelle, inkl. Test-Button.
- **Mehrsprachige Analyse**: automatische Spracherkennung (heuristisch, ohne zusätzliche
  Abhängigkeit) oder feste Sprache für die Analyse-Prompts.

## Installation

**Windows:** `install.bat` doppelklicken (oder `powershell -ExecutionPolicy Bypass -File install.ps1`).
**Linux/macOS:** `./install.sh`.

Das Skript legt eine virtuelle Umgebung an, installiert alle Abhängigkeiten, erzeugt eine `.env`
mit generiertem Verschlüsselungs-Schlüssel und zeigt an, wie die App gestartet wird.

Manuell geht es natürlich auch:

```bash
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\Activate.ps1
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

Beim ersten Start erklärt ein Willkommens-Dialog kurz die Einrichtung und führt in den
Einstellungen-Tab (Mail-Konto + Ollama konfigurieren, dann "Speichern").

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
  Report-, Benchmark-, Webhook-, Sprach- und Chat-Service
- `mailorganizer/ui` – PyQt6-Hauptfenster (Tab-Layout), Widgets (Ordner-Baum, Cleanup-Vorschau,
  Bericht, Benchmark, Chat mit Trefferliste, Einstellungen mit Unterreitern, Onboarding), eigene
  QPainter-Chart-Widgets (Pie/Bar, ohne matplotlib), Dark/Light-Themes, `workers.py`
  (Hintergrund-Threading für alle blockierenden Operationen)
- `mailorganizer/utils` – Logging, Exceptions, Validierung, Krypto-Helfer, Mail-Utils
- `tests` – Unit-Tests für alle Services + UI-Hilfsmodule (86 Tests, laufen headless per
  `conftest.py`, kein Display nötig)
- `install.sh` / `install.ps1` / `install.bat` – Installations-Skripte für Linux/macOS/Windows

### Analyse-Regeln: Bedingungsformat

Jede Regel hat genau eine Bedingung, gespeichert als JSON in `analysis_rules.condition`:

```json
{"field": "sender", "operator": "contains", "value": "amazon", "set_category": "shopping"}
```

- `field`: `sender` | `subject` | `category` | `importance_score` | `sentiment` | `keywords`
- `operator`: `contains` | `equals` | `gt` | `lt` | `gte` | `lte`
- `set_category`: nur relevant, wenn `action == "category"`

## Design-Entscheidungen

Gemäß Plan-Abschnitt 16 ("Dependencies Minimieren") wurden Charts, PDF-Export und der Chat
bewusst ohne neue Abhängigkeiten umgesetzt: die Kreis-/Balkendiagramme sind selbst geschriebene
QPainter-Widgets (`ui/widgets/charts.py`), der PDF-Export nutzt Qt's eingebauten `QPdfWriter`,
die Spracherkennung ist eine leichte Stopword-Heuristik statt einer ML-Bibliothek, und der
Chat-Assistent nutzt einen selbst geschriebenen Tool-Calling-Loop auf Basis des bestehenden
`/api/generate`-Endpunkts (`chat_service.py`) statt eines separaten Function-Calling-APIs —
funktioniert dadurch mit jedem lokalen Ollama-Modell, nicht nur mit Modellen, die natives
Tool-Calling unterstützen. Alle bisherigen Requirements (`requirements.txt`) sind unverändert
ausreichend.

Bestehende Datenbanken werden beim ersten Start automatisch migriert (`_migrate_schema` in
`models/database.py`, z. B. die neue `folder`-Spalte per `ALTER TABLE`) — kein manueller Schritt
nötig, kein Alembic für diese einfachen Änderungen erforderlich.

## Offene Punkte (nächste Phasen)

Nicht umgesetzt (aus Plan-Abschnitt 8.5/13): Mobile-Companion-App (eigenständiges,
plattformübergreifendes Projekt außerhalb dieses Repos), ein programmatischer REST-API-Endpunkt
für externe Automatisierung (das Webhook-Feature deckt den "Mail Organizer → extern"-Weg bereits
ab), sowie Alembic-Migrationen (aktuell reicht `create_all` für das MVP-Schema).
