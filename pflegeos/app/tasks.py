"""
Geplante Aufgaben für PflegeOS.
Läuft täglich um 08:00 Uhr und prüft Geburtstage + religiöse Feiertage.

In Produktion (gunicorn): APScheduler wird genutzt.
In Entwicklung (flask run): manueller Trigger über /greetings/trigger-check.
"""
import logging
import os
import threading
from datetime import date, datetime, timedelta

logger = logging.getLogger(__name__)
_scheduler_thread = None


# ── Morgendliche Glückwunsch-Prüfung ─────────────────────────────────────────

def run_morning_greetings_check(app):
    """
    Haupttask: Läuft täglich um 08:00.
    Für jeden aktiven Patienten prüfen ob heute ein Feiertag / Geburtstag ist.
    Falls ja → KI-Nachricht generieren und in DB speichern.
    """
    with app.app_context():
        from app.models import Patient, PatientGreeting
        from app.utils.holiday_calendar import get_todays_events
        from app.services.greeting_service import generate_greeting
        from app.extensions import db

        today = date.today()
        logger.info(f"[Morning Check] Starte Glückwunsch-Prüfung für {today}")

        patients = Patient.query.filter_by(deleted_at=None, status='AKTIV').all()
        generated = 0

        for patient in patients:
            # Bereits heute generierte Grüße überspringen
            already = PatientGreeting.query.filter(
                PatientGreeting.patient_id == patient.id,
                db.func.date(PatientGreeting.created_at) == today
            ).first()
            if already:
                continue

            events = get_todays_events(patient, today)
            for event in events:
                try:
                    message = generate_greeting(patient, event['name'], event['type'])
                    greeting = PatientGreeting(
                        patient_id=patient.id,
                        company_id=patient.company_id,
                        occasion=event['name'],
                        occasion_type=event['type'],
                        message=message,
                    )
                    db.session.add(greeting)
                    db.session.flush()
                    generated += 1
                    logger.info(f"  ✓ {patient.full_name} → {event['name']}")
                except Exception as e:
                    logger.error(f"  ✗ Fehler bei {patient.full_name} / {event['name']}: {e}")

        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            logger.error(f"[Morning Check] DB-Fehler beim Commit: {e}")

        logger.info(f"[Morning Check] Abgeschlossen: {generated} neue Grüße generiert.")


# ── Täglicher Schlaf-Loop ─────────────────────────────────────────────────────

def _daily_loop(app):
    """
    Hintergrundthread: schläft bis 08:00 und löst den Check aus.
    Läuft endlos bis das Programm beendet wird.
    """
    logger.info("✓ Täglicher Glückwunsch-Scheduler gestartet (nächster Check um 08:00)")
    while True:
        try:
            now = datetime.now()
            # Nächsten 08:00 berechnen
            target = now.replace(hour=8, minute=0, second=0, microsecond=0)
            if now >= target:
                target += timedelta(days=1)  # morgen 08:00
            wait = (target - now).total_seconds()
            logger.debug(f"[Scheduler] Nächster Check in {wait/3600:.1f}h um {target.strftime('%d.%m.%Y 08:00')}")
            threading.Event().wait(timeout=wait)
            run_morning_greetings_check(app)
        except Exception as e:
            logger.error(f"[Scheduler] Fehler im Loop: {e} — retry in 60s")
            threading.Event().wait(timeout=60)


# ── Scheduler initialisieren ─────────────────────────────────────────────────

def init_scheduler(app):
    """
    Startet den täglichen Hintergrund-Thread.
    - Im Debug-Modus mit Werkzeug-Reloader: nur im Child-Prozess starten.
    - In Produktion (gunicorn): immer starten.
    """
    global _scheduler_thread

    # Werkzeug Reloader: nur im Child-Prozess starten (WERKZEUG_RUN_MAIN='true')
    # In Produktion (gunicorn) ist WERKZEUG_RUN_MAIN nicht gesetzt → starten
    if app.debug and os.environ.get('WERKZEUG_RUN_MAIN') != 'true':
        logger.debug("[Scheduler] Übersprungen — Werkzeug Parent-Prozess")
        return

    if _scheduler_thread is not None and _scheduler_thread.is_alive():
        logger.debug("[Scheduler] Läuft bereits")
        return

    _scheduler_thread = threading.Thread(
        target=_daily_loop,
        args=(app,),
        daemon=True,
        name='GlueckwunschScheduler'
    )
    _scheduler_thread.start()


def trigger_manual_check(app):
    """Manueller Auslöser für Tests / Admin-Interface (läuft synchron)."""
    run_morning_greetings_check(app)
