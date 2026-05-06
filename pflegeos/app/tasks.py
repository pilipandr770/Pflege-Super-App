"""
Geplante Aufgaben für PflegeOS.
Läuft täglich um 08:00 Uhr und prüft:
  • Geburtstage + religiöse Feiertage → KI-Glückwünsche
  • TÜV/HU-Frist & Versicherung Ablauf (≤ 30 Tage) → Admin-Alerts

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
