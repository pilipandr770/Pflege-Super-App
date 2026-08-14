"""
Geplante Aufgaben für PflegeOS.
Läuft täglich um 08:00 Uhr und prüft:
  • Geburtstage + religiöse Feiertage → KI-Glückwünsche
  • TÜV/HU-Frist & Versicherung Ablauf (≤ 30 Tage) → Admin-Alerts

In Entwicklung (flask run): manueller Trigger über /greetings/trigger-check.
"""
import logging
import os
from datetime import date, datetime, timedelta

logger = logging.getLogger(__name__)
_scheduler = None


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
        run_fuhrpark_alerts_check(app)


# ── Fuhrpark-Frist-Check ──────────────────────────────────────────────────────

def run_fuhrpark_alerts_check(app):
    """
    Prüft für alle Fahrzeuge ob TÜV/HU oder Versicherung in ≤ 30 Tagen abläuft
    bzw. bereits abgelaufen ist → sendet E-Mail-Alerts an alle Admins der Company.
    """
    with app.app_context():
        from app.models import Fahrzeug, Employee
        from app.extensions import mail
        from flask_mail import Message

        today = date.today()
        logger.info(f"[Fuhrpark-Check] Starte Frist-Prüfung für {today}")

        fahrzeuge = Fahrzeug.query.filter_by(deleted_at=None).all()

        # Sammle Probleme pro Company
        company_problems: dict = {}  # company_id → list of (fahrzeug, label, msg)
        # Auch überfällige Wartungen prüfen
        from app.models import Wartungseintrag
        seen_w = set()
        for w in Wartungseintrag.query.join(Fahrzeug).filter(
            Fahrzeug.company_id.in_([fz.company_id for fz in fahrzeuge]),
            Fahrzeug.deleted_at == None,
            Wartungseintrag.naechster_termin != None,
        ).all():
            if w.faellig_status in ('expired', 'critical', 'warning'):
                key = (w.fahrzeug_id, w.art)
                if key not in seen_w:
                    seen_w.add(key)
                    if w.faellig_status == 'expired':
                        company_problems.setdefault(w.fahrzeug.company_id, []).append(
                            f"{w.fahrzeug.kennzeichen}: Wartung '{w.art_label}' überfällig seit {w.naechster_termin.strftime('%d.%m.%Y')}!"
                        )
                    else:
                        company_problems.setdefault(w.fahrzeug.company_id, []).append(
                            f"{w.fahrzeug.kennzeichen}: Wartung '{w.art_label}' fällig in {w.faellig_tage} Tagen ({w.naechster_termin.strftime('%d.%m.%Y')})"
                        )

        for fz in fahrzeuge:
            checks = [
                ('TÜV/HU', fz.tuev_bis, fz.tuev_tage, fz.tuev_status),
                ('Versicherung', fz.versicherung_bis, fz.versicherung_tage, fz.versicherung_status),
            ]
            for label, ablauf_datum, tage, status in checks:
                if ablauf_datum is None or status not in ('expired', 'critical', 'warning'):
                    continue

                if status == 'expired':
                    msg = (f"{fz.kennzeichen}: {label} abgelaufen am "
                           f"{ablauf_datum.strftime('%d.%m.%Y')}!")
                else:
                    msg = (f"{fz.kennzeichen}: {label} läuft in {tage} Tagen ab "
                           f"({ablauf_datum.strftime('%d.%m.%Y')})")

                company_problems.setdefault(fz.company_id, []).append(msg)
                logger.warning(f"[Fuhrpark-Check] {msg}")

        if not company_problems:
            logger.info("[Fuhrpark-Check] Keine ablaufenden Fristen heute.")
            return

        emails_sent = 0
        for company_id, problems in company_problems.items():
            admins = Employee.query.filter_by(
                company_id=company_id,
                role='ADMIN',
                is_active=True
            ).filter(Employee.email.isnot(None)).all()

            body_lines = [f"⚠️  Fuhrpark-Frist-Warnung — {today.strftime('%d.%m.%Y')}", ""]
            body_lines += [f"• {p}" for p in problems]
            body_lines += ["", "Bitte die betroffenen Fahrzeuge im Fuhrpark-Modul prüfen."]
            body = "\n".join(body_lines)

            for admin in admins:
                try:
                    msg_obj = Message(
                        subject=f"⚠️ Fuhrpark-Alert: {len(problems)} Frist(en) ablaufend",
                        recipients=[admin.email],
                        body=body,
                    )
                    mail.send(msg_obj)
                    emails_sent += 1
                except Exception as e:
                    logger.error(f"[Fuhrpark-Check] E-Mail-Fehler an {admin.email}: {e}")

        logger.info(f"[Fuhrpark-Check] Abgeschlossen: {emails_sent} Alerts versendet.")


# ── APScheduler-Initialisierung ───────────────────────────────────────────────

def init_scheduler(app):
    """
    Startet APScheduler mit einem täglichen Cron-Job um 08:00.
    - Im Debug-Modus mit Werkzeug-Reloader: nur im Child-Prozess starten,
      um doppelte Jobs zu vermeiden.
    - In Produktion (gunicorn --workers 1): läuft sicher in einem Prozess.
    """
    global _scheduler

    if app.debug and os.environ.get('WERKZEUG_RUN_MAIN') != 'true':
        logger.debug("[Scheduler] Übersprungen — Werkzeug Parent-Prozess")
        return

    if _scheduler is not None and _scheduler.running:
        logger.debug("[Scheduler] Läuft bereits")
        return

    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.cron import CronTrigger

    _scheduler = BackgroundScheduler(timezone='Europe/Berlin')
    _scheduler.add_job(
        func=run_morning_greetings_check,
        trigger=CronTrigger(hour=8, minute=0, timezone='Europe/Berlin'),
        args=[app],
        id='morning_check',
        name='Täglicher Glückwunsch- und Fuhrpark-Check',
        replace_existing=True,
        misfire_grace_time=3600,
    )
    _scheduler.start()
    logger.info("✓ APScheduler gestartet — Täglicher Check um 08:00 Europe/Berlin")


def trigger_manual_check(app):
    """Manueller Auslöser für Tests / Admin-Interface (läuft synchron)."""
    run_morning_greetings_check(app)
