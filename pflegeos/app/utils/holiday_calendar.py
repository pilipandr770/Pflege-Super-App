"""
Feiertagskalender für PflegeOS.
Gibt für einen Patienten (basierend auf Religion + Nationalität + Geburtsdatum)
alle relevanten Ereignisse für das heutige Datum zurück.
"""
from datetime import date


# ── Easter-Berechnung (Gauss/Spencer-Jones-Algorithmus) ─────────────────────

def _easter(year: int) -> date:
    """Berechnet Ostersonntag für ein gegebenes Jahr (westlich/gregorianisch)."""
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day   = ((h + l - 7 * m + 114) % 31) + 1
    return date(year, month, day)


def _orthodox_easter(year: int) -> date:
    """Berechnet orthodoxes Osterfest (Julian → Gregorian)."""
    a = year % 4
    b = year % 7
    c = year % 19
    d = (19 * c + 15) % 30
    e = (2 * a + 4 * b - d + 34) % 7
    month = (d + e + 114) // 31
    day   = ((d + e + 114) % 31) + 1
    # Julian → Gregorian Korrektur (ab 1900: +13 Tage)
    from datetime import timedelta
    return date(year, month, day) + timedelta(days=13)


# ── Christliche Feiertage (feste Daten) ────────────────────────────────────

def _christian_holidays(year: int) -> list:
    easter = _easter(year)
    from datetime import timedelta
    events = [
        {'date': date(year, 1, 1),  'name': 'Neujahr'},
        {'date': date(year, 1, 6),  'name': 'Heilige Drei Könige'},
        {'date': easter - timedelta(days=46), 'name': 'Aschermittwoch'},
        {'date': easter - timedelta(days=7),  'name': 'Palmsonntag'},
        {'date': easter - timedelta(days=3),  'name': 'Gründonnerstag'},
        {'date': easter - timedelta(days=2),  'name': 'Karfreitag'},
        {'date': easter,                      'name': 'Ostersonntag'},
        {'date': easter + timedelta(days=1),  'name': 'Ostermontag'},
        {'date': easter + timedelta(days=39), 'name': 'Christi Himmelfahrt'},
        {'date': easter + timedelta(days=49), 'name': 'Pfingstsonntag'},
        {'date': easter + timedelta(days=50), 'name': 'Pfingstmontag'},
        {'date': easter + timedelta(days=60), 'name': 'Fronleichnam'},
        {'date': date(year, 8, 15),  'name': 'Mariä Himmelfahrt'},
        {'date': date(year, 10, 3),  'name': 'Tag der deutschen Einheit'},
        {'date': date(year, 11, 1),  'name': 'Allerheiligen'},
        {'date': date(year, 12, 24), 'name': 'Heiligabend'},
        {'date': date(year, 12, 25), 'name': 'Erster Weihnachtstag'},
        {'date': date(year, 12, 26), 'name': 'Zweiter Weihnachtstag'},
        {'date': date(year, 12, 31), 'name': 'Silvester'},
    ]
    return events


def _orthodox_holidays(year: int) -> list:
    oe = _orthodox_easter(year)
    from datetime import timedelta
    return [
        {'date': date(year, 1, 7),  'name': 'Orthodoxes Weihnachten'},
        {'date': date(year, 1, 19), 'name': 'Orthodoxe Taufe Jesu (Theophanie)'},
        {'date': oe - timedelta(days=2), 'name': 'Orthodoxer Karfreitag'},
        {'date': oe,                     'name': 'Orthodoxes Osterfest'},
        {'date': oe + timedelta(days=1), 'name': 'Orthodoxer Ostermontag'},
        {'date': oe + timedelta(days=39),'name': 'Orthodoxe Himmelfahrt'},
        {'date': oe + timedelta(days=49),'name': 'Orthodoxes Pfingstfest'},
    ]


# ── Islamische Feiertage (pre-berechnet 2025–2030) ──────────────────────────
# Daten können leicht abweichen (Mondkalender), Näherungswerte

_ISLAMIC_HOLIDAYS = {
    2025: [
        {'date': date(2025, 3, 30), 'name': 'Eid al-Fitr (Ende Ramadan)'},
        {'date': date(2025, 3, 31), 'name': 'Eid al-Fitr (Ende Ramadan)'},
        {'date': date(2025, 6, 7),  'name': 'Eid al-Adha (Opferfest)'},
        {'date': date(2025, 6, 8),  'name': 'Eid al-Adha (Opferfest)'},
        {'date': date(2025, 6, 27), 'name': 'Islamisches Neujahr (Muharram)'},
        {'date': date(2025, 9, 4),  'name': 'Mawlid an-Nabi (Geburtstag des Propheten)'},
    ],
    2026: [
        {'date': date(2026, 3, 20), 'name': 'Eid al-Fitr (Ende Ramadan)'},
        {'date': date(2026, 5, 27), 'name': 'Eid al-Adha (Opferfest)'},
        {'date': date(2026, 6, 17), 'name': 'Islamisches Neujahr (Muharram)'},
        {'date': date(2026, 8, 25), 'name': 'Mawlid an-Nabi (Geburtstag des Propheten)'},
    ],
    2027: [
        {'date': date(2027, 3, 9),  'name': 'Eid al-Fitr (Ende Ramadan)'},
        {'date': date(2027, 5, 17), 'name': 'Eid al-Adha (Opferfest)'},
        {'date': date(2027, 6, 6),  'name': 'Islamisches Neujahr (Muharram)'},
        {'date': date(2027, 8, 14), 'name': 'Mawlid an-Nabi (Geburtstag des Propheten)'},
    ],
    2028: [
        {'date': date(2028, 2, 26), 'name': 'Eid al-Fitr (Ende Ramadan)'},
        {'date': date(2028, 5, 5),  'name': 'Eid al-Adha (Opferfest)'},
        {'date': date(2028, 5, 25), 'name': 'Islamisches Neujahr (Muharram)'},
        {'date': date(2028, 8, 3),  'name': 'Mawlid an-Nabi (Geburtstag des Propheten)'},
    ],
    2029: [
        {'date': date(2029, 2, 14), 'name': 'Eid al-Fitr (Ende Ramadan)'},
        {'date': date(2029, 4, 24), 'name': 'Eid al-Adha (Opferfest)'},
        {'date': date(2029, 5, 14), 'name': 'Islamisches Neujahr (Muharram)'},
        {'date': date(2029, 7, 23), 'name': 'Mawlid an-Nabi (Geburtstag des Propheten)'},
    ],
    2030: [
        {'date': date(2030, 2, 4),  'name': 'Eid al-Fitr (Ende Ramadan)'},
        {'date': date(2030, 4, 13), 'name': 'Eid al-Adha (Opferfest)'},
        {'date': date(2030, 5, 3),  'name': 'Islamisches Neujahr (Muharram)'},
        {'date': date(2030, 7, 12), 'name': 'Mawlid an-Nabi (Geburtstag des Propheten)'},
    ],
}


# ── Jüdische Feiertage (pre-berechnet 2025–2030) ───────────────────────────

_JEWISH_HOLIDAYS = {
    2025: [
        {'date': date(2025, 4, 12), 'name': 'Schabbat HaGadol (Pessach-Vorbereitung)'},
        {'date': date(2025, 4, 13), 'name': 'Pessach (Passahfest)'},
        {'date': date(2025, 4, 14), 'name': 'Pessach (Passahfest)'},
        {'date': date(2025, 6, 1),  'name': 'Schawuot (Wochenfest)'},
        {'date': date(2025, 9, 22), 'name': 'Rosch Haschana (Jüdisches Neujahr)'},
        {'date': date(2025, 9, 23), 'name': 'Rosch Haschana (Jüdisches Neujahr)'},
        {'date': date(2025, 10, 1), 'name': 'Jom Kippur (Versöhnungstag)'},
        {'date': date(2025, 10, 6), 'name': 'Sukkot (Laubhüttenfest)'},
        {'date': date(2025, 12, 14),'name': 'Chanukka'},
        {'date': date(2025, 12, 15),'name': 'Chanukka'},
        {'date': date(2025, 12, 22),'name': 'Chanukka (letzter Tag)'},
    ],
    2026: [
        {'date': date(2026, 4, 1),  'name': 'Pessach (Passahfest)'},
        {'date': date(2026, 5, 20), 'name': 'Schawuot (Wochenfest)'},
        {'date': date(2026, 9, 11), 'name': 'Rosch Haschana (Jüdisches Neujahr)'},
        {'date': date(2026, 9, 20), 'name': 'Jom Kippur (Versöhnungstag)'},
        {'date': date(2026, 12, 4), 'name': 'Chanukka'},
    ],
    2027: [
        {'date': date(2027, 3, 21), 'name': 'Pessach (Passahfest)'},
        {'date': date(2027, 5, 9),  'name': 'Schawuot (Wochenfest)'},
        {'date': date(2027, 10, 1), 'name': 'Rosch Haschana (Jüdisches Neujahr)'},
        {'date': date(2027, 10, 10),'name': 'Jom Kippur (Versöhnungstag)'},
        {'date': date(2027, 12, 24),'name': 'Chanukka'},
    ],
    2028: [
        {'date': date(2028, 4, 10), 'name': 'Pessach (Passahfest)'},
        {'date': date(2028, 5, 28), 'name': 'Schawuot (Wochenfest)'},
        {'date': date(2028, 9, 20), 'name': 'Rosch Haschana (Jüdisches Neujahr)'},
        {'date': date(2028, 9, 29), 'name': 'Jom Kippur (Versöhnungstag)'},
        {'date': date(2028, 12, 12),'name': 'Chanukka'},
    ],
}


# ── Hinduistische Feiertage (pre-berechnet 2025–2028) ──────────────────────

_HINDU_HOLIDAYS = {
    2025: [
        {'date': date(2025, 3, 14), 'name': 'Holi (Frühlingsfest)'},
        {'date': date(2025, 3, 30), 'name': 'Ram Navami'},
        {'date': date(2025, 4, 6),  'name': 'Hanuman Jayanti'},
        {'date': date(2025, 10, 20),'name': 'Diwali (Lichterfest)'},
        {'date': date(2025, 10, 21),'name': 'Diwali (Lichterfest)'},
        {'date': date(2025, 10, 22),'name': 'Diwali (Lichterfest)'},
        {'date': date(2025, 11, 5), 'name': 'Diwali Nachfeier (Bhai Dooj)'},
    ],
    2026: [
        {'date': date(2026, 3, 3),  'name': 'Holi (Frühlingsfest)'},
        {'date': date(2026, 10, 9), 'name': 'Diwali (Lichterfest)'},
        {'date': date(2026, 10, 10),'name': 'Diwali (Lichterfest)'},
    ],
    2027: [
        {'date': date(2027, 3, 22), 'name': 'Holi (Frühlingsfest)'},
        {'date': date(2027, 10, 29),'name': 'Diwali (Lichterfest)'},
    ],
    2028: [
        {'date': date(2028, 3, 11), 'name': 'Holi (Frühlingsfest)'},
        {'date': date(2028, 10, 17),'name': 'Diwali (Lichterfest)'},
    ],
}


# ── Buddhistische Feiertage ─────────────────────────────────────────────────

_BUDDHIST_HOLIDAYS = {
    2025: [
        {'date': date(2025, 5, 12), 'name': 'Vesak (Geburtstag Buddhas)'},
        {'date': date(2025, 7, 10), 'name': 'Dhamma Day (Asalha Puja)'},
    ],
    2026: [
        {'date': date(2026, 5, 31), 'name': 'Vesak (Geburtstag Buddhas)'},
    ],
    2027: [
        {'date': date(2027, 5, 20), 'name': 'Vesak (Geburtstag Buddhas)'},
    ],
    2028: [
        {'date': date(2028, 5, 8),  'name': 'Vesak (Geburtstag Buddhas)'},
    ],
}


# ── Religions-Erkennung (Fuzzy) ─────────────────────────────────────────────

def _religion_category(religion: str) -> str:
    """Klassifiziert den Freitext-Religionswert in eine Kategorie."""
    if not religion:
        return 'unknown'
    r = religion.lower().strip()
    if any(k in r for k in ('christl', 'kathol', 'evangel', 'protest', 'christ', 'baptist', 'lutheran')):
        return 'christian'
    if any(k in r for k in ('orthodox', 'griech', 'russisch-orth', 'serbisch', 'rumänisch-orth')):
        return 'orthodox'
    if any(k in r for k in ('islam', 'muslim', 'moslem', 'sunni', 'schiit')):
        return 'islamic'
    if any(k in r for k in ('jüdisch', 'judent', 'jewish', 'jude', 'hebr')):
        return 'jewish'
    if any(k in r for k in ('hindu', 'sindh', 'vaishn', 'shaiv')):
        return 'hindu'
    if any(k in r for k in ('buddh', 'zen', 'theravad', 'mahayana')):
        return 'buddhist'
    return 'unknown'


# ── Hauptfunktion ────────────────────────────────────────────────────────────

def get_todays_events(patient, today: date = None) -> list:
    """
    Gibt alle relevanten Ereignisse für einen Patienten am heutigen Tag zurück.

    Rückgabe: Liste von Dicts:
        {
            'name': str,          # z.B. "Ostersonntag", "Geburtstag", "Eid al-Fitr"
            'type': str,          # 'birthday' | 'religious' | 'national'
            'religion': str,      # welche Religion es betrifft
        }
    """
    if today is None:
        today = date.today()

    events = []
    year = today.year

    # ── 1. Geburtstag ────────────────────────────────────────────────────────
    if patient.geburtsdatum:
        bday = patient.geburtsdatum
        if bday.month == today.month and bday.day == today.day:
            age = year - bday.year
            events.append({
                'name': f'Geburtstag ({age}. Geburtstag)',
                'type': 'birthday',
                'religion': 'alle',
            })

    # ── 2. Religiöse Feiertage ───────────────────────────────────────────────
    cat = _religion_category(patient.religion)

    if cat == 'christian':
        for h in _christian_holidays(year):
            if h['date'] == today:
                events.append({'name': h['name'], 'type': 'religious', 'religion': 'christlich'})

    elif cat == 'orthodox':
        for h in _orthodox_holidays(year):
            if h['date'] == today:
                events.append({'name': h['name'], 'type': 'religious', 'religion': 'orthodox-christlich'})
        # Orthodoxe feiern auch manche westlichen Feiertage
        for h in [{'date': date(year, 1, 1), 'name': 'Neujahr'}]:
            if h['date'] == today:
                events.append({'name': h['name'], 'type': 'religious', 'religion': 'orthodox-christlich'})

    elif cat == 'islamic':
        for h in _ISLAMIC_HOLIDAYS.get(year, []):
            if h['date'] == today:
                events.append({'name': h['name'], 'type': 'religious', 'religion': 'islamisch'})

    elif cat == 'jewish':
        for h in _JEWISH_HOLIDAYS.get(year, []):
            if h['date'] == today:
                events.append({'name': h['name'], 'type': 'religious', 'religion': 'jüdisch'})

    elif cat == 'hindu':
        for h in _HINDU_HOLIDAYS.get(year, []):
            if h['date'] == today:
                events.append({'name': h['name'], 'type': 'religious', 'religion': 'hinduistisch'})

    elif cat == 'buddhist':
        for h in _BUDDHIST_HOLIDAYS.get(year, []):
            if h['date'] == today:
                events.append({'name': h['name'], 'type': 'religious', 'religion': 'buddhistisch'})

    # ── 3. Universelle Feiertage (alle Religionen) ──────────────────────────
    universal = [
        date(year, 1, 1),   # Neujahr
        date(year, 12, 24), # Heiligabend — für alle
        date(year, 12, 25), # Weihnachten — für alle
    ]
    if cat == 'unknown' and today in universal:
        label = {
            date(year, 1, 1):   'Neujahr',
            date(year, 12, 24): 'Heiligabend',
            date(year, 12, 25): 'Weihnachten',
        }[today]
        events.append({'name': label, 'type': 'national', 'religion': 'alle'})

    return events
