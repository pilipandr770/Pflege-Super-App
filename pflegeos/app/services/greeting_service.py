"""
KI-gestützte Glückwunsch-Generierung für Patienten.
Verwendet Anthropic Claude API für personalisierte, kulturell sensible Nachrichten.
"""
import logging
from flask import current_app
from app.extensions import mail, db
from flask_mail import Message

logger = logging.getLogger(__name__)


# ── Anlass-spezifische Hinweise für das Prompt ──────────────────────────────

_OCCASION_HINTS = {
    'Geburtstag': (
        'herzlichen Geburtstagsglückwunsch. '
        'Betone Lebensfreude, Gesundheit und die Fürsorge des Teams.'
    ),
    'Weihnachten': (
        'frohe Weihnachten. '
        'Betone Wärme, Familie, Frieden und Licht in der dunklen Jahreszeit.'
    ),
    'Heiligabend': (
        'einen besinnlichen Heiligabend. '
        'Betone Stille, Vorfreude und Geborgenheit.'
    ),
    'Ostersonntag': (
        'frohe Ostern. '
        'Betone Auferstehung, Hoffnung, Frühling und neues Leben.'
    ),
    'Eid al-Fitr': (
        'Eid Mubarak zum Ende des Ramadans. '
        'Betone Freude nach dem Fasten, Dankbarkeit, Gemeinschaft und Frieden.'
    ),
    'Eid al-Adha': (
        'gesegnetes Opferfest (Eid al-Adha). '
        'Betone Opferbereitschaft, Glaube, Gemeinschaft und Segen.'
    ),
    'Rosch Haschana': (
        'ein gutes neues Jahr (Schana Towa). '
        'Betone Erneuerung, Reflexion, Süße des Lebens und Hoffnung.'
    ),
    'Jom Kippur': (
        'einen bedeutsamen Jom Kippur. '
        'Betone Besinnung, Vergebung und inneren Frieden — respektvoll und ruhig.'
    ),
    'Chanukka': (
        'ein frohes Chanukka-Fest. '
        'Betone Licht in der Dunkelheit, Wunder, Freude und Gemeinschaft.'
    ),
    'Diwali': (
        'ein frohes Diwali-Lichterfest. '
        'Betone Licht über Dunkelheit, Freude, Wohlstand und neuen Anfang.'
    ),
    'Holi': (
        'ein fröhliches Holi-Frühlingsfest. '
        'Betone Farben, Freude, Erneuerung und Gemeinschaft.'
    ),
    'Vesak': (
        'einen gesegneten Vesak-Tag (Geburtstag Buddhas). '
        'Betone Mitgefühl, inneren Frieden, Erleuchtung und Dankbarkeit.'
    ),
    'Pessach': (
        'ein befreiendes Pessach-Fest. '
        'Betone Freiheit, Gemeinschaft, Erinnerung und Hoffnung.'
    ),
    'Neujahr': (
        'ein frohes neues Jahr. '
        'Betone frischen Start, Gesundheit, Glück und gute Wünsche.'
    ),
    'Orthodoxes Weihnachten': (
        'frohe orthodoxe Weihnachten (Rozhdestvo). '
        'Betone Licht, Freude, Geburt Christi und Gemeinschaft.'
    ),
    'Orthodoxes Osterfest': (
        'ein freudiges orthodoxes Osterfest (Christos Voskrese). '
        'Betone Auferstehung, Licht, Freude und Hoffnung.'
    ),
}


def _get_hint(occasion: str) -> str:
    """Gibt den passenden Anlass-Hinweis zurück (auch bei Teil-Übereinstimmung)."""
    for key, hint in _OCCASION_HINTS.items():
        if key.lower() in occasion.lower():
            return hint
    return f'zum Anlass: {occasion}. Betone Freude, Gesundheit und Wohlbefinden.'


def generate_greeting(patient, occasion: str, occasion_type: str) -> str:
    """
    Generiert mit Claude eine personalisierte Glückwunschnachricht.
    Gibt den generierten Text zurück.
    """
    import anthropic

    api_key = current_app.config.get('ANTHROPIC_API_KEY')
    if not api_key:
        logger.warning("ANTHROPIC_API_KEY nicht konfiguriert — verwende Fallback-Nachricht")
        return _fallback_greeting(patient, occasion)

    hint = _get_hint(occasion)

    # Sprache bestimmen (Muttersprache des Patienten)
    lang_note = ''
    if patient.sprache_muttersprache and patient.sprache_muttersprache.lower() not in ('deutsch', 'german', 'de'):
        lang_note = (
            f'Schreibe die Nachricht auf Deutsch, '
            f'füge aber optional einen kurzen Gruß in der Muttersprache hinzu '
            f'({patient.sprache_muttersprache}).'
        )

    prompt = f"""Du bist ein einfühlsamer Mitarbeiter eines deutschen Pflegedienstes.
Schreibe eine kurze, herzliche und persönliche Glückwunschnachricht auf Deutsch für:

Patient: {patient.vorname} {patient.nachname}
Anlass: {occasion}
Religion: {patient.religion or 'nicht angegeben'}
Nationalität: {patient.nationalitaet or 'nicht angegeben'}

Deine Aufgabe: Schreibe einen {hint}

Regeln:
- Verwende den Vornamen des Patienten
- Maximal 3 Sätze
- Warm, respektvoll und aufbauend — keine Floskeln
- Die Nachricht kommt von "Ihrem Pflegeteam"
- {lang_note if lang_note else 'Nur auf Deutsch'}
- Keine Betreffzeile, kein "Liebe/r" am Anfang — direkt der Text
- Kein Abschluss wie "Mit freundlichen Grüßen"

Gib NUR den Nachrichtentext aus, ohne Erklärungen."""

    try:
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model='claude-opus-4-5',
            max_tokens=250,
            messages=[{'role': 'user', 'content': prompt}]
        )
        text = response.content[0].text.strip()
        logger.info(f"Greeting generated for {patient.full_name}: {occasion}")
        return text
    except Exception as e:
        logger.error(f"Anthropic API error for {patient.full_name}: {e}")
        return _fallback_greeting(patient, occasion)


def _fallback_greeting(patient, occasion: str) -> str:
    """Einfache Fallback-Nachricht ohne KI."""
    return (
        f"Liebe/r {patient.vorname}, "
        f"zu {occasion} wünscht Ihnen Ihr Pflegeteam alles Gute, "
        f"Gesundheit und viel Freude. 🌸"
    )


def send_greeting_email(greeting) -> bool:
    """
    Sendet eine Glückwunschnachricht per E-Mail an den Betreuer des Patienten.
    Gibt True zurück wenn erfolgreich.
    """
    patient = greeting.patient
    recipient = patient.betreuer_email
    if not recipient:
        logger.info(f"Kein Betreuer-E-Mail für {patient.full_name} — E-Mail nicht gesendet")
        return False

    try:
        from flask import render_template
        html = render_template(
            'emails/greeting.html',
            patient=patient,
            occasion=greeting.occasion,
            message=greeting.message,
        )
        msg = Message(
            subject=f'🎉 {greeting.occasion} – Grüße für {patient.vorname}',
            recipients=[recipient],
            html=html,
            sender=current_app.config.get('MAIL_DEFAULT_SENDER', 'noreply@pflegeos.local'),
        )
        mail.send(msg)
        logger.info(f"Greeting email sent to {recipient} for {patient.full_name}: {greeting.occasion}")
        return True
    except Exception as e:
        logger.error(f"Failed to send greeting email for {patient.full_name}: {e}")
        return False
