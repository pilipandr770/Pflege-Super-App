"""
Glückwunsch-Center — Admin sieht alle KI-generierten Grüße des Tages.
Kann E-Mail an Betreuer senden (wenn betreuer_email vorhanden).
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app
from flask_login import login_required, current_user
from app.models import PatientGreeting, Patient
from app.extensions import db
from datetime import date, timedelta

greetings_bp = Blueprint('greetings', __name__, url_prefix='/greetings')


def _admin_required():
    if not current_user.is_admin:
        from flask import abort
        abort(403)


@greetings_bp.route('/')
@login_required
def today():
    """Zeigt alle Grüße des heutigen Tages für die eigene Company."""
    _admin_required()
    cid = current_user.company_id

    # Filter: today / last 7 days
    period = request.args.get('period', 'today')
    if period == 'week':
        since = date.today() - timedelta(days=7)
        greetings = PatientGreeting.query.filter(
            PatientGreeting.company_id == cid,
            PatientGreeting.created_at >= since,
        ).order_by(PatientGreeting.created_at.desc()).all()
    else:
        greetings = PatientGreeting.query.filter(
            PatientGreeting.company_id == cid,
            db.func.date(PatientGreeting.created_at) == date.today(),
        ).order_by(PatientGreeting.created_at.desc()).all()

    return render_template('greetings/today.html',
                           greetings=greetings,
                           period=period,
                           today=date.today())


@greetings_bp.route('/<int:greeting_id>/send-email', methods=['POST'])
@login_required
def send_email(greeting_id):
    """Sendet die Glückwunschmail an den Betreuer des Patienten."""
    _admin_required()
    cid = current_user.company_id

    greeting = PatientGreeting.query.filter_by(
        id=greeting_id,
        company_id=cid
    ).first_or_404()

    if greeting.sent_email:
        flash('Diese Nachricht wurde bereits per E-Mail versendet.', 'warning')
        return redirect(url_for('greetings.today'))

    from app.services.greeting_service import send_greeting_email
    from datetime import datetime

    ok = send_greeting_email(greeting)
    if ok:
        greeting.sent_email = True
        greeting.sent_at = datetime.utcnow()
        db.session.commit()
        flash(f'✓ Glückwunsch an {greeting.patient.betreuer_email} gesendet.', 'success')
    else:
        flash('E-Mail konnte nicht gesendet werden. Bitte prüfen Sie die Mail-Konfiguration.', 'danger')

    return redirect(url_for('greetings.today'))


@greetings_bp.route('/trigger-check', methods=['POST'])
@login_required
def trigger_check():
    """Manuell die morgendliche Prüfung auslösen (für Tests)."""
    _admin_required()
    try:
        from app.tasks import trigger_manual_check
        trigger_manual_check(current_app._get_current_object())
        flash('✓ Glückwunsch-Prüfung wurde manuell ausgelöst.', 'success')
    except Exception as e:
        flash(f'Fehler: {e}', 'danger')
    return redirect(url_for('greetings.today'))


@greetings_bp.route('/count-today')
@login_required
def count_today():
    """JSON-Endpunkt: Anzahl heutiger Grüße (für Dashboard-Badge)."""
    cid = current_user.company_id
    count = PatientGreeting.query.filter(
        PatientGreeting.company_id == cid,
        db.func.date(PatientGreeting.created_at) == date.today(),
    ).count()
    return jsonify({'count': count})
