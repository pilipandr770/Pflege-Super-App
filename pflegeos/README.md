# PflegeOS MVP

**SaaS-Dokumentationssystem für Pflegeeinrichtungen**
Stationär, ambulant, Tagespflege | DSGVO-konform | BtMG §13 | SGB XI/V

---

## 🚀 Schnellstart (Lokal)

### Voraussetzungen
- Python 3.11+
- PostgreSQL 15+ (oder Docker)
- pip

### 1. Umgebung einrichten

```bash
cd pflegeos

# Virtuelle Umgebung
python -m venv venv
source venv/bin/activate         # Windows: venv\Scripts\activate

# Abhängigkeiten
pip install -r requirements.txt
```

### 2. Konfiguration

```bash
cp .env.example .env
# .env öffnen und ausfüllen:
# - DATABASE_URL
# - SECRET_KEY  (beliebiger langer String)
# - ENCRYPTION_KEY (Fernet-Key generieren — siehe unten)
```

**Fernet-Key generieren:**
```python
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

### 3. Datenbank starten (Docker)

```bash
docker-compose up -d db
# Wartet ~5 Sekunden bis PostgreSQL bereit ist
```

Oder eigene PostgreSQL-Instanz — dann DATABASE_URL in .env anpassen.

### 4. Datenbank migrieren

```bash
flask db init       # nur beim ersten Mal
flask db migrate -m "Initial"
flask db upgrade
```

### 5. App starten

```bash
flask run
# Öffnen: http://localhost:5000
```

### 6. Erste Einrichtung registrieren

1. http://localhost:5000/auth/register öffnen
2. Einrichtungsdaten eingeben
3. Admin-Konto anlegen
4. Anmelden

### 7. Leistungskatalog befüllen

```bash
flask seed
```
Fügt 33 Standard-SGB-XI-Leistungen für alle registrierten Einrichtungen ein.

---

## 📁 Projektstruktur

```
pflegeos/
├── app/
│   ├── __init__.py          # App-Factory
│   ├── config.py            # Konfiguration (dev/prod)
│   ├── extensions.py        # Flask-Erweiterungen
│   ├── models/
│   │   └── __init__.py      # Alle Datenbankmodelle
│   ├── routes/
│   │   ├── auth.py          # Login, Logout, Registrierung
│   │   ├── dashboard.py     # Startseite mit Statistiken
│   │   ├── patients.py      # Patientenverwaltung
│   │   ├── sis.py           # SIS-Dokumentation
│   │   ├── medications.py   # Medikamente + BtM
│   │   ├── leistung.py      # Leistungsnachweis
│   │   ├── wounds.py        # Wunddokumentation
│   │   └── company.py       # Einstellungen, Mitarbeiter
│   ├── utils/
│   │   └── auth.py          # Dekoratoren, Audit-Log, Upload
│   └── templates/           # Jinja2-Templates (Bootstrap 5 + HTMX)
├── uploads/                 # Hochgeladene Dateien (nicht in Git!)
├── .env.example             # Umgebungsvariablen-Vorlage
├── docker-compose.yml       # PostgreSQL für lokale Entwicklung
├── requirements.txt
├── run.py                   # Einstiegspunkt
└── seed.py                  # Standard-Leistungskatalog
```

---

## 🔒 Sicherheitskonzept

| Feature | Umsetzung |
|---|---|
| Passwörter | bcrypt (12 Runden) |
| Session | HttpOnly + SameSite=Lax |
| CSRF | Flask-WTF auf allen POST-Formularen |
| Audit-Log | Unveränderlich, jede Aktion protokolliert |
| BtM-Verifikation | Vier-Augen-Prinzip + PIN |
| GPS-Verifikation | Browser Geolocation API |
| Multi-Tenant | Row Level Security via company_id |
| Uploads | UUID-Dateinamen, Extension-Whitelist |

---

## 📋 Enthaltene Module (MVP)

- ✅ Unternehmensregistrierung + Multi-Tenant Auth
- ✅ Patientenverwaltung (vollständig)
- ✅ SIS — Strukturierte Informationssammlung (6 Blöcke)
- ✅ Medikationsplan + Verabreichungsdokumentation
- ✅ BtM-Buch (§13 BtMG, Vier-Augen-Prinzip)
- ✅ Leistungsnachweis (SGB XI) + Leistungskatalog
- ✅ Wunddokumentation + Fotodokumentation + Trendberechnung
- ✅ Mitarbeiterverwaltung + Rollensystem + PIN
- ✅ GPS-Verifikation (automatisch im Browser)
- ✅ Audit-Log (alle Aktionen)

---

## 🛣️ Nächste Schritte (Phase 2)

- [ ] Sturzprotokoll-Modul
- [ ] Pflegebericht (Freitextdokumentation pro Schicht)
- [ ] Fahrtenbuch (ambulante Dienste)
- [ ] PDF-Export (SIS, Leistungsnachweis, BtM-Buch)
- [ ] E-Mail-Benachrichtigungen
- [ ] Schichtplanung / Kalender
- [ ] KI-Assistent (anonymisiert via ai_token)

---

## 🐛 Bekannte Limitierungen (MVP)

- Foto-Vorschau in Wunddokumentation benötigt statischen Dateiserver
- Kein E-Mail-Versand ohne SMTP-Konfiguration
- BtM-Buch: Mitarbeiter-Relationen (mitarbeiter_1, mitarbeiter_2) noch nicht vollständig verknüpft
- NFC: Backend-Validierung noch nicht implementiert

---

## 📞 Support

**Entwickler:** Andrii Pylypchuk | AndriiIT
**E-Mail:** [Ihre E-Mail]
