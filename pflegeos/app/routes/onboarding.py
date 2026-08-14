"""
Onboarding-Wizard: führt neue Admins in 3 Schritten durch die Ersteinrichtung.
Wird nur angezeigt, solange company.onboarding_completed == False.
"""
from flask import (Blueprint, render_template, redirect, url_for, flash,
                   request, session)
from flask_login import login_required, current_user
from app.extensions import db
from app.models import Company, Employee, Patient
from app.utils.auth import log_action

onboarding_bp = Blueprint('onboarding', __name__, url_prefix='/onboarding')

STEPS = [
    {'nr': 1, 'slug': 'firma',       'title': 'Firmendaten vervollständigen'},
    {'nr': 2, 'slug': 'mitarbeiter', 'title': 'Ersten Mitarbeiter anlegen'},
    {'nr': 3, 'slug': 'patient',     'title': 'Ersten Patienten anlegen'},
]


def _company():
    return Company.query.get(current_user.company_id)


def _onboarding_required(f):
    from functools import wraps
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            return redirect(url_for('dashboard.index'))
        c = _company()
        if c and c.onboarding_completed:
            return redirect(url_for('dashboard.index'))
        return f(*args, **kwargs)
    return wrapper


@onboarding_bp.route('/')
@login_required
@_onboarding_required
def start():
    return redirect(url_for('onboarding.step', slug='firma'))


@onboarding_bp.route('/schritt/<slug>', methods=['GET', 'POST'])
@login_required
@_onboarding_required
def step(slug):
    step_obj = next((s for s in STEPS if s['slug'] == slug), None)
    if not step_obj:
        return redirect(url_for('onboarding.step', slug='firma'))

    company = _company()

    if request.method == 'POST' and slug == 'firma':
        company.ik_nummer   = request.form.get('ik_nummer', '').strip() or company.ik_nummer
        company.pdl_name    = request.form.get('pdl_name', '').strip() or company.pdl_name
        company.telefon     = request.form.get('telefon', '').strip() or company.telefon
        company.geschaeftsfuehrer_name = (
            request.form.get('gf_name', '').strip() or company.geschaeftsfuehrer_name
        )
        db.session.commit()
        return redirect(url_for('onboarding.step', slug='mitarbeiter'))

    if request.method == 'POST' and slug == 'mitarbeiter':
        # Weitermachen – Mitarbeiter wird über normalen /company/employees/new angelegt
        return redirect(url_for('onboarding.step', slug='patient'))

    if request.method == 'POST' and slug == 'patient':
        return redirect(url_for('onboarding.finish'))

    # Fortschritt berechnen
    employee_count = Employee.query.filter_by(
        company_id=company.id, deleted_at=None
    ).count()
    patient_count = Patient.query.filter_by(
        company_id=company.id, deleted_at=None
    ).count()

    return render_template(
        f'onboarding/{slug}.html',
        step=step_obj,
        steps=STEPS,
        company=company,
        employee_count=employee_count,
        patient_count=patient_count,
    )


@onboarding_bp.route('/abschluss')
@login_required
def finish():
    company = _company()
    if company and not company.onboarding_completed:
        company.onboarding_completed = True
        db.session.commit()
        log_action('ONBOARDING_COMPLETED', 'companies', company.id)
    flash('Einrichtung abgeschlossen! Willkommen bei PflegeOS.', 'success')
    return render_template('onboarding/done.html', company=company)


@onboarding_bp.route('/ueberspringen')
@login_required
def skip():
    """Admin kann Onboarding jederzeit überspringen."""
    company = _company()
    if company:
        company.onboarding_completed = True
        db.session.commit()
    return redirect(url_for('dashboard.index'))
