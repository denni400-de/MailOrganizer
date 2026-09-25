# Mail Organizer mit Ollama - Professioneller Implementierungsplan

## 1. Projektübersicht & Zielsetzung

### Hauptziele
- Intelligente E-Mail-Verwaltung durch lokale LLM-Integration (Ollama)
- Benutzerfreundliche GUI mit Echtzeit-Vorschau
- Sichere Verwaltung von Mail-Konten
- Automatische Kategorisierung und Archivierung
- Interaktive Kommunikation zwischen KI und Benutzer über Mail-Wichtigkeit

### Zielgruppe
- Power-User mit großer Mailmenge
- Datenschutzbewusste Nutzer (alles lokal)
- Berufliche und private Nutzung

---

## 2. Technologie-Stack

### Backend
- **Python 3.11+** - Hauptsprache
- **PyQt6** oder **PySimpleGUI** - Desktop-GUI (empfohlen: PyQt6)
- **imapclient** - IMAP-Verbindung
- **smtplib** - E-Mail-Versand
- **requests** - Ollama-API-Kommunikation
- **sqlalchemy** - Datenbankabstraktion
- **sqlite3** - Lokale Persistierung
- **python-dotenv** - Umgebungsvariablen
- **pydantic** - Datenvalidierung
- **logging** - Professionelles Logging

### Externe Services
- **Ollama** (lokal) - LLM für Mail-Analyse
- **IMAP/SMTP-Server** - E-Mail-Provider

### Datenbank
- **SQLite** für lokale Persistierung (schnell, keine externe DB nötig)
- Migration Support mit **Alembic** (für Skalierbarkeit)

---

## 3. Architektur & Komponenten

### 3.1 Projektstruktur

```
MailOrganizer/
├── mailorganizer/
│   ├── __init__.py
│   ├── main.py                    # Einstiegspunkt
│   ├── config/
│   │   ├── __init__.py
│   │   ├── settings.py            # Globale Konfiguration
│   │   └── constants.py           # Konstanten
│   ├── models/
│   │   ├── __init__.py
│   │   ├── database.py            # SQLAlchemy ORM-Modelle
│   │   ├── mail.py                # Mail-Datenclassen
│   │   └── analysis.py            # Analyse-Ergebnisse
│   ├── services/
│   │   ├── __init__.py
│   │   ├── mail_service.py        # IMAP/SMTP-Operationen
│   │   ├── ollama_service.py      # Ollama-Integration
│   │   ├── analysis_service.py    # Mail-Analyse-Logik
│   │   ├── storage_service.py     # Datenbankoperationen
│   │   └── scheduler_service.py   # Background-Tasks
│   ├── ui/
│   │   ├── __init__.py
│   │   ├── main_window.py         # Hauptfenster
│   │   ├── widgets/
│   │   │   ├── __init__.py
│   │   │   ├── settings_panel.py  # Einstellungs-Dialog
│   │   │   ├── mail_list.py       # Mail-Tabelle
│   │   │   ├── preview_panel.py   # Mail-Vorschau
│   │   │   ├── analysis_panel.py  # Analyse-Ergebnisse
│   │   │   └── status_bar.py      # Status-Anzeige
│   │   └── styles/
│   │       ├── __init__.py
│   │       ├── dark_theme.qss     # Dark Mode Stylesheet
│   │       └── light_theme.qss    # Light Mode Stylesheet
│   ├── utils/
│   │   ├── __init__.py
│   │   ├── logger.py              # Logging-Setup
│   │   ├── exceptions.py          # Benutzerdefinierte Exceptions
│   │   ├── validators.py          # Input-Validierung
│   │   └── email_utils.py         # Email-Hilfsfunktionen
│   └── migrations/
│       └── alembic/               # Datenbankmigrationen
├── tests/
│   ├── __init__.py
│   ├── test_mail_service.py
│   ├── test_ollama_service.py
│   ├── test_analysis_service.py
│   └── fixtures/
├── requirements.txt
├── setup.py
├── .env.example
└── README.md
```

### 3.2 Kernkomponenten

#### A. Mail-Service (IMAP/SMTP)
**Funktionen:**
- Verbindung mit IMAP-Servern
- Abrufen von Mails (mit Pagination)
- Senden von E-Mails
- Verschieben/Löschen von Mails
- Flaggen setzen (read, important, archived)
- Sichere Speicherung von Credentials

#### B. Ollama-Service
**Funktionen:**
- Verbindung zu lokalem Ollama-Server
- Modell-Management (verfügbare Modelle auflisten)
- Prompt-Engineering für Mail-Analyse
- Streaming-Response-Verarbeitung
- Error-Handling bei Ollama-Ausfällen

#### C. Analysis-Service
**Funktionen:**
- Mail-Metadaten extrahieren
- LLM-basierte Analyse durchführen
- Kategorisierung (Spam, Work, Personal, Bills, etc.)
- Wichtigkeit bewerten (1-5 Skala)
- Empfohlene Aktionen generieren
- Sentiment-Analyse durchführen

#### D. Storage-Service
**Funktionen:**
- Persistierung von Mail-Metadaten
- Analyse-Ergebnisse speichern
- Benutzer-Einstellungen verwalten
- Ollama-Model-Historie speichern
- Query-Interface für UI

#### E. Scheduler-Service
**Funktionen:**
- Regelmäßiges Abrufen neuer Mails
- Automatische Analyse von neuen Mails
- Hintergrund-Cleanup
- Berichte generieren

---

## 4. Datenbankschema

### Tabellen

#### `users`
```sql
CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    imap_server TEXT NOT NULL,
    imap_port INTEGER DEFAULT 993,
    smtp_server TEXT NOT NULL,
    smtp_port INTEGER DEFAULT 587,
    email_address TEXT UNIQUE NOT NULL,
    password_encrypted TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### `mails`
```sql
CREATE TABLE mails (
    id INTEGER PRIMARY KEY,
    message_id TEXT UNIQUE NOT NULL,
    user_id INTEGER NOT NULL,
    sender TEXT NOT NULL,
    recipients TEXT NOT NULL,        -- JSON
    cc TEXT,                         -- JSON
    subject TEXT NOT NULL,
    body TEXT,
    html_body TEXT,
    received_at TIMESTAMP NOT NULL,
    is_read BOOLEAN DEFAULT 0,
    is_archived BOOLEAN DEFAULT 0,
    is_important BOOLEAN DEFAULT 0,
    is_spam BOOLEAN DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
```

#### `mail_analysis`
```sql
CREATE TABLE mail_analysis (
    id INTEGER PRIMARY KEY,
    mail_id INTEGER NOT NULL UNIQUE,
    category TEXT,                  -- "work", "personal", "bills", "spam", etc.
    importance_score INTEGER,       -- 1-5
    sentiment TEXT,                 -- "positive", "neutral", "negative"
    summary TEXT,
    recommended_action TEXT,        -- "archive", "flag", "delete", "reply"
    keywords TEXT,                  -- JSON array
    ollama_model TEXT NOT NULL,
    analysis_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    processing_time_ms INTEGER,
    FOREIGN KEY (mail_id) REFERENCES mails(id) ON DELETE CASCADE
);
```

#### `settings`
```sql
CREATE TABLE settings (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL,
    key TEXT NOT NULL,
    value TEXT NOT NULL,
    UNIQUE(user_id, key),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
```

#### `ollama_config`
```sql
CREATE TABLE ollama_config (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL,
    ollama_url TEXT DEFAULT 'http://localhost:11434',
    ollama_model TEXT NOT NULL,
    temperature REAL DEFAULT 0.7,
    max_tokens INTEGER DEFAULT 500,
    last_checked TIMESTAMP,
    is_available BOOLEAN DEFAULT 1,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
```

#### `analysis_rules`
```sql
CREATE TABLE analysis_rules (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    condition TEXT NOT NULL,        -- JSON: pattern matching rules
    action TEXT NOT NULL,           -- "archive", "delete", "flag", "category"
    priority INTEGER DEFAULT 1,
    is_active BOOLEAN DEFAULT 1,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
```

---

## 5. GUI-Design & Workflow

### 5.1 Hauptfenster-Layout

```
┌─────────────────────────────────────────────────────────┐
│ Menu: Datei | Bearbeiten | Ansicht | Tools | Hilfe     │
├──────────────────────────────────────────────────────────┤
│ [⚙️ Einstellungen] [🔄 Sync] [🗑️ Cleanup] [📊 Bericht]   │
├──────────────────────────────────────────────────────────┤
│ Mail-Liste (Tabelle)      │  Vorschau-Panel            │
│ ─────────────────────────│─────────────────────────   │
│ Von | Betreff | Datum   │  Absender: xxxx@xx.com     │
│ ─────────────────────────│  Datum: DD.MM.YYYY         │
│ [Mail 1]                 │                            │
│ [Mail 2]                 │  Betreff: xxxxxxxxxx      │
│ [Mail 3]                 │  ────────────────────────  │
│ [Mail 4]                 │  Mail-Body...              │
│                          │                            │
│                          │  Analyse-Ergebnisse:       │
│                          │  ┌──────────────────────┐  │
│                          │  │ Kategorie: Work      │  │
│                          │  │ Wichtigkeit: ⭐⭐⭐⭐  │  │
│                          │  │ Sentiment: Positiv   │  │
│                          │  │ Aktion: Archivieren  │  │
│                          │  └──────────────────────┘  │
├──────────────────────────────────────────────────────────┤
│ Status: ✅ Verbunden | Mails: 42 | Neu: 3              │
└──────────────────────────────────────────────────────────┘
```

### 5.2 Einstellungs-Dialog

**Tab 1: Mail-Einstellungen**
- IMAP-Server, Port, E-Mail, Passwort
- SMTP-Server, Port
- Auto-Sync Intervall (5m, 15m, 30m, 1h)
- Verbindungs-Test Button
- Sichere Speicherung (verschlüsseltes Passwort)

**Tab 2: Ollama-Konfiguration**
- Ollama-Server-URL (Standard: http://localhost:11434)
- Verfügbare Modelle (Dropdown, Refresh-Button)
- Temperatur (Slider: 0.0 - 1.0)
- Max Tokens (Input: 100-2000)
- Modell-Test Button
- Verbindungs-Status

**Tab 3: Analyse-Regeln**
- Benutzerdefinierte Kategorien
- Auto-Archiv-Regeln basierend auf Sender/Betreff
- Spam-Filter-Konfiguration
- Keyword-basierte Kategorisierung

**Tab 4: UI-Einstellungen**
- Dark/Light Mode
- Schriftgröße
- Spalten-Sichtbarkeit
- Update-Benachrichtigungen

### 5.3 Workflows

#### Workflow 1: Erste Einrichtung
1. App startet → Einstellungs-Dialog (falls keine Config)
2. User gibt Mail-Daten ein
3. Verbindungs-Test durchführen
4. Ollama-Verbindung prüfen
5. Modell-Auswahl
6. Synchronisierung starten

#### Workflow 2: Tägliche Nutzung
1. Auto-Sync aktiviert → neue Mails abrufen
2. Mails in Tabelle angezeigt (neueste oben)
3. User klickt auf Mail → Vorschau + Analyse
4. User kann: Archivieren, Löschen, Flaggen, Manual Review
5. Empfohlene Aktion mit 1-Klick ausführen

#### Workflow 3: Mail-Cleanup
1. User klickt "Cleanup"
2. Dialog mit Optionen:
   - Alte Mails archivieren (älter als X Tage)
   - Spam löschen
   - Doppelte löschen
   - Nach Wichtigkeit sortiert anzeigen
3. Bestätigung vor Aktion
4. Fortschrittsbalken während Verarbeitung
5. Zusammenfassung nach Abschluss

---

## 6. KI-Analyse-Engine

### 6.1 Prompt-Engineering

#### System-Prompt
```
Du bist ein professioneller Mail-Analyst. Analysiere die folgende E-Mail 
und liefere eine strukturierte Analyse.

Antworte IMMER in diesem exakten JSON-Format:
{
    "category": "work|personal|bills|news|shopping|spam|other",
    "importance_score": 1-5,
    "sentiment": "positive|neutral|negative",
    "summary": "Kurze 1-2 Satz Zusammenfassung",
    "recommended_action": "archive|flag|delete|reply|read_later",
    "keywords": ["keyword1", "keyword2"],
    "reasoning": "Kurze Erklärung der Entscheidungen"
}
```

#### User-Prompt Template
```
Analysiere diese E-Mail:

Von: {sender}
Betreff: {subject}
Datum: {date}
---
{body_excerpt}

Beachte:
- Dies ist E-Mail #{email_number} von {sender}
- User Sprache: {user_language}
- Benutzer-Kontext: {user_preferences}
```

### 6.2 Analyse-Kategorien

| Kategorie | Beschreibung | Aktion |
|-----------|-------------|--------|
| **work** | Arbeitsmails | Flag, Archiv nach Datum |
| **personal** | Freunde, Familie | Behalten, Normal |
| **bills** | Rechnungen, Abos | Flag, Speichern |
| **news** | Newsletter | Auto-Archiv nach Lesen |
| **shopping** | Bestellbestätigungen | Archiv nach Lieferung |
| **spam** | Unerwünschte Mails | Auto-Löschen |
| **other** | Sonstiges | Manuell |

### 6.3 Wichtigkeits-Skala

- ⭐ (1) - Später lesen
- ⭐⭐ (2) - Normal
- ⭐⭐⭐ (3) - Wichtig
- ⭐⭐⭐⭐ (4) - Sehr wichtig
- ⭐⭐⭐⭐⭐ (5) - Sofort handeln erforderlich

### 6.4 Benutzerdefinierte Intelligenz

**Learning from User Actions:**
- Wenn User ignoriert die empfohlene Aktion → Note in Datenbank
- Nach 10 ähnlichen Mails → Prompt anpassen
- Benutzer-Feedback-Buttons in der UI

---

## 7. Sicherheit & Datenschutz

### 7.1 Passwort-Management
- **Encryption**: `cryptography.fernet` für Passwort-Speicherung
- **Master-Password**: Optional für zusätzliche Sicherheit
- **SSL/TLS**: Für IMAP/SMTP-Verbindungen erzwingen

### 7.2 Lokale Daten
- Alle Mails werden lokal in SQLite gespeichert
- Datenbankdatei verschlüssbar
- Regelmäßige Backups ermöglichen
- Option: Export/Import von Daten

### 7.3 Ollama-Privacy
- Ollama läuft lokal → keine Daten-Transmission zu extern
- Mails bleiben auf dem Gerät des Benutzers

### 7.4 Best Practices
- Logging ohne sensitive Daten
- Rate-Limiting bei API-Aufrufen
- Input-Validierung (Regex, Length-Checks)
- SQL-Injection-Prävention (Parameterized Queries)

---

## 8. Erweiterte Funktionen

### 8.1 Intelligente Filterung

**Conditional Rules Engine:**
```python
{
    "if_sender_contains": ["amazon", "ebay"],
    "then_category": "shopping",
    "and_archive_after_days": 30
}
```

**Smart Folders (virtuelle Ordner):**
- "Wichtige von heute"
- "Unbearbeitete Arbeits-Mails"
- "Zu zahlende Rechnungen"
- "Zu lesende Newsletter"

### 8.2 Bericht-Generation

**Wöchentlicher Bericht:**
- Top Sender/Domains
- Kategorie-Statistik (Pie Chart)
- Wichtigkeits-Verteilung
- Vorgeschlagene Aufräum-Aktionen
- Export als PDF

### 8.3 Batch-Processing

**Funktionen:**
- Alle Mails von Sender archivieren
- Bulk-Kategorisierung
- Backup erstellen
- Duplikate entfernen

### 8.4 Ollama-Model-Benchmarking

**Vergleich von Modellen:**
- Gleiche Mails mit verschiedenen Modellen analysieren
- Genauigkeit vergleichen
- Performance-Metriken (ms pro Mail)
- Benutzer-Feedback sammeln

### 8.5 Integration für External Services (Optional)

- **Slack/Discord-Benachrichtigungen**: Bei wichtigen Mails
- **Webhook-Support**: Für externe Automatisierung
- **API-Endpunkt**: Zur programmatischen Nutzung

### 8.6 Sprach-Unterstützung

- Automatische Spracherkennung von Mails
- Multi-Sprachen-Analyse (Deutsch, Englisch, etc.)
- Sprach-Einstellung in Preferences

---

## 9. Performance-Optimierungen

### 9.1 Caching
- Ollama-Responses cachen (gleiche Mail → gleiche Analyse)
- Sender-Profile cachen (wiederkehrende Sender)
- UI-State cachen

### 9.2 Batch-Verarbeitung
- Mehrere Mails gleichzeitig laden
- Analysis-Queue für Background-Processing
- Thread-Pool für parallele Verarbeitung

### 9.3 Datenbank
- Indices auf häufig gefilterten Spalten
- Paginated Abfragen in der UI
- Archive alte Mails (älter als 1 Jahr)

### 9.4 UI-Responsiveness
- Long-Running Tasks in Threads
- Progress-Dialoge mit Cancel-Option
- Lazy-Loading von Mail-Vorschaubildern

---

## 10. Error-Handling & Robustheit

### 10.1 Fehlerszenarien

| Fehler | Handling |
|--------|----------|
| IMAP-Verbindung fehlgeschlagen | Retry-Logic, Fallback auf Cache |
| Ollama nicht erreichbar | Warnung, Manual-Review-Modus |
| Ungültiges Passwort | Fehler-Dialog, Re-Entry |
| Netzwerk-Fehler | Offline-Modus mit Sync pending |
| Korrupte Datenbank | Backup-Recovery |
| Zu viele Mails | Pagination, Limiting |

### 10.2 Logging & Monitoring

```python
# Detailliertes Logging
logger.info("Mail sync started for {}", email)
logger.error("IMAP connection failed", exc_info=True)
logger.debug("Analysis completed in {} ms", duration)
```

**Log-Datei:** `~/.mailorganizer/logs/app.log`

---

## 11. Implementierungs-Roadmap

### Phase 1: Basis (Woche 1-2)
- ✅ Projektstruktur aufbauen
- ✅ Database-Setup mit SQLite
- ✅ Mail-Service (IMAP-Connect, Abrufen)
- ✅ Basis-GUI mit PyQt6
- ✅ Settings-Dialog

### Phase 2: Ollama-Integration (Woche 3)
- ✅ Ollama-Service implementieren
- ✅ Analysis-Service mit Prompts
- ✅ Analyse-Speicherung in DB
- ✅ Preview-Panel mit Analyse-Anzeige

### Phase 3: Intelligente Features (Woche 4-5)
- ✅ Benutzerdefinierte Kategorien
- ✅ Auto-Actions (Archivieren, Löschen)
- ✅ Cleanup-Funktion
- ✅ Batch-Processing

### Phase 4: UX & Polish (Woche 6)
- ✅ Fehlerbehandlung verfeinern
- ✅ UI/UX-Verbesserungen
- ✅ Styling (Dark/Light Mode)
- ✅ Doku & Beispiele

### Phase 5: Advanced (Optional)
- ✅ Reporting & Charts
- ✅ Model-Benchmarking
- ✅ External-Integrations
- ✅ Mobile-Companion-App

---

## 12. Testing-Strategie

### Unit Tests
```python
test_mail_service.py
- test_imap_connection()
- test_mail_fetching()
- test_mail_parsing()

test_ollama_service.py
- test_ollama_connection()
- test_prompt_generation()
- test_response_parsing()

test_analysis_service.py
- test_categorization()
- test_importance_scoring()
```

### Integration Tests
- Mail + DB + UI zusammen testen
- Ollama + Analysis Pipeline
- User-Workflows simulieren

### UI Tests (Selenium/PyTest)
- Dialog-Interaktionen
- Mail-Selection & Preview
- Settings speichern

### Performance Tests
- 10.000 Mails laden
- Batch-Analyse von 100 Mails
- Memory-Usage Monitor

---

## 13. Deployment & Distribution

### Packaging

**Option A: Standalone Executable**
```bash
pyinstaller --onefile --windowed mailorganizer/main.py
```

**Option B: Package via pip**
```bash
pip install mail-organizer
```

**Option C: Docker Container** (für Server-Nutzung)
```dockerfile
FROM python:3.11
WORKDIR /app
COPY . .
RUN pip install -r requirements.txt
CMD ["python", "-m", "mailorganizer"]
```

### System Requirements
- Python 3.11+
- 4GB RAM (min), 8GB+ empfohlen
- Ollama installiert & läuft
- 2GB freier Speicher (für DB & Cache)
- Linux, macOS oder Windows 10+

---

## 14. Konfigurationsdatei (.env.example)

```env
# Mail Settings
IMAP_SERVER=imap.gmail.com
IMAP_PORT=993
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587

# Ollama Settings
OLLAMA_URL=http://localhost:11434
OLLAMA_MODEL=mistral:latest
OLLAMA_TEMPERATURE=0.7
OLLAMA_MAX_TOKENS=500

# App Settings
AUTO_SYNC_INTERVAL=300  # Sekunden
LOG_LEVEL=INFO
UI_THEME=dark
DATABASE_PATH=~/.mailorganizer/data.db

# Security
ENCRYPT_PASSWORDS=true
BACKUP_ENABLED=true
BACKUP_FREQUENCY=weekly
```

---

## 15. Häufig gestellte Fragen & Solutions

### F: Wie kann ich die Analyse-Genauigkeit verbessern?
**A:** 
- Modell-Wechsel testen (z.B. neural-chat statt mistral)
- User-Feedback sammeln und Prompts anpassen
- Kategorien erweitern basierend auf tatsächlichem Usage

### F: Kann ich meine Mails exportieren?
**A:** Ja, Export-Funktion in Menü:
- CSV Export der Mail-Liste
- PDF-Report
- MBOX-Format für Archivierung

### F: Funktioniert das auch offline?
**A:** Teilweise:
- Gespeicherte Mails können ohne Netz gelesen werden
- Neue Analysen brauchen Ollama-Zugriff
- Sync erfolgt bei Netzwerk-Rückverbindung

---

## 16. Entwickler-Notizen

### Code-Standards
- **Type Hints** überall
- **Docstrings** für alle Klassen & Funktionen
- **Constants** in `constants.py`
- **Logger** statt print()
- **Exception Handling** in jedem Service

### Key Design Patterns
- **Singleton Pattern**: Für Mail-Service, Ollama-Service
- **Observer Pattern**: Für DB-Changes → UI-Updates
- **Strategy Pattern**: Für verschiedene Analyse-Strategien
- **Factory Pattern**: Für Mail-Objekt-Erstellung

### Dependencies Minimieren
- Nur essenzielle externe Libraries
- Eigne UI-Components schreiben statt External Libs
- Ollama als einzige "schwere" Abhängigkeit

---

## Zusammenfassung

Dies ist ein **produktionsreifes Konzept** für einen intelligenten Mail-Organizer:

✅ **Vollständig**: Von Setup bis automatische Wartung
✅ **Sicher**: Lokale Verarbeitung, verschlüsselte Credentials
✅ **Skalierbar**: SQLite → PostgreSQL möglich
✅ **Benutzerfreundlich**: Intuitive GUI mit Vorschau
✅ **Intelligent**: Ollama-basierte Analyse mit Learning
✅ **Erweiterbar**: APIs für Custom-Rules & Integrationen

Die Implementierung kann inkrementell erfolgen - starten Sie mit Phase 1 und erweitern Sie sukzessive!
