from flask import Blueprint, render_template
from flask_login import login_required, current_user
from app.models import Patient, SisAssessment, MedicationAdministration, Leistungsnachweis, MedicationPlan, WoundDoc, EmployeeSchedule
from datetime import date, timedelta, datetime

dashboard_bp = Blueprint('dashboard', __name__)


def get_missing_docs():
    """Find active patients with missing critical documentation for insurance billing."""
    cid = current_user.company_id
    missing_docs = []

    active_patients = Patient.query.filter_by(
        company_id=cid, status='AKTIV', deleted_at=None
    ).all()

    for patient in active_patients:
        missing = []

        # Check for current SIS assessment
        current_sis = SisAssessment.query.filter_by(
            patient_id=patient.id, company_id=cid, is_current=True, status='COMPLETED'
        ).first()
        if not current_sis:
            missing.append('SIS-Einschätzung')

        # Check for active wound docs if patient has dekubitus risk
        if patient.dekubitusrisiko:
            active_wounds = WoundDoc.query.filter_by(
                patient_id=patient.id, company_id=cid, is_active=True
            ).all()
            for wound in active_wounds:
                recent_assessment = WoundDoc.query.join(
                    WoundDoc.assessments
                ).filter(
                    WoundDoc.id == wound.id,
                    WoundDoc.company_id == cid
                ).first()
                if not recent_assessment or not recent_assessment.assessments.first():
                    missing.append(f'Wundbeurteilung: {wound.wunde_bezeichnung}')
                    break

        if missing:
            missing_docs.append({
                'patient': patient,
                'missing': missing
            })

    return missing_docs


@dashboard_bp.route('/')
@login_required
def index():
    cid = current_user.company_id
    today = date.today()

    stats = {
        'patienten_aktiv': Patient.query.filter_by(company_id=cid, status='AKTIV', deleted_at=None).count(),
        'sis_offen': SisAssessment.query.filter_by(company_id=cid, status='DRAFT', is_current=True).count(),
        'medikamente_heute': MedicationAdministration.query.filter(
            MedicationAdministration.company_id == cid,
            MedicationAdministration.administered_at >= today
        ).count(),
        'leistungen_heute': Leistungsnachweis.query.filter(
            Leistungsnachweis.company_id == cid,
            Leistungsnachweis.durchgefuehrt_am == today
        ).count(),
    }

    if current_user.is_admin:
        # Пациенты требующие внимания (риски) — только для админа
        risiko_patienten = Patient.query.filter_by(
            company_id=cid, status='AKTIV', deleted_at=None
        ).filter(
            (Patient.sturzrisiko == True) |
            (Patient.dekubitusrisiko == True)
        ).limit(5).all()

        # Пациенты с недостающей документацией — только для админа
        docs_missing = get_missing_docs()

        nurse_schedule_today = []
    else:
        # Для полевого персонала — план на сегодня
        risiko_patienten = []
        docs_missing = []
        nurse_schedule_today = EmployeeSchedule.query.filter_by(
            employee_id=current_user.id,
            company_id=cid,
            scheduled_date=today,
            is_active=True
        ).order_by(EmployeeSchedule.scheduled_time).all()

        # Nur eigene Leistungen heute zählen
        stats['leistungen_heute'] = Leistungsnachweis.query.filter(
            Leistungsnachweis.company_id == cid,
            Leistungsnachweis.employee_id == current_user.id,
            Leistungsnachweis.durchgefuehrt_am == today
        ).count()

    # Check if user is on first login
    is_first_login = current_user.last_login_at is None or (
        current_user.updated_at and
        (datetime.utcnow() - current_user.last_login_at).total_seconds() < 60
    )

    return render_template('dashboard/index.html',
                           stats=stats,
                           risiko_patienten=risiko_patienten,
                           docs_missing=docs_missing,
                           nurse_schedule_today=nurse_schedule_today,
                           is_first_login=is_first_login,
                           today=today)
