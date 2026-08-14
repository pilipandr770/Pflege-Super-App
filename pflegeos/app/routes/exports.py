from flask import Blueprint, send_file, abort, current_app, request
from flask_login import login_required, current_user
from app.models import Patient, SisAssessment, MedicationPlan, Leistungsnachweis, Company
from app.utils.pdf import (generate_patient_summary_pdf, generate_sis_assessment_pdf,
                            generate_medication_plan_pdf, generate_leistungsnachweis_pdf)
from datetime import datetime, date
from calendar import monthrange

export_bp = Blueprint('exports', __name__, url_prefix='/exports')


@export_bp.route('/patient/<patient_id>/summary.pdf')
@login_required
def patient_summary_pdf(patient_id):
    """Export patient summary as PDF."""
    patient = Patient.query.filter_by(
        id=patient_id, company_id=current_user.company_id, deleted_at=None
    ).first_or_404()

    try:
        pdf_buffer = generate_patient_summary_pdf(patient)
        return send_file(
            pdf_buffer,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=f"{patient.full_name.replace(' ', '_')}_Zusammenfassung_{datetime.now().strftime('%Y%m%d')}.pdf"
        )
    except Exception as e:
        current_app.logger.error(f"PDF generation error: {str(e)}")
        abort(500)


@export_bp.route('/sis/<sis_id>.pdf')
@login_required
def sis_assessment_pdf(sis_id):
    """Export SIS assessment as PDF."""
    sis = SisAssessment.query.filter_by(
        id=sis_id, company_id=current_user.company_id
    ).first_or_404()

    patient = sis.patient
    if patient.company_id != current_user.company_id:
        abort(403)

    try:
        pdf_buffer = generate_sis_assessment_pdf(patient, sis)
        return send_file(
            pdf_buffer,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=f"{patient.full_name.replace(' ', '_')}_SIS_{sis.assessment_date.strftime('%Y%m%d')}.pdf"
        )
    except Exception as e:
        current_app.logger.error(f"PDF generation error: {str(e)}")
        abort(500)


@export_bp.route('/medication-plan/<plan_id>.pdf')
@login_required
def medication_plan_pdf(plan_id):
    """Export medication plan as PDF."""
    plan = MedicationPlan.query.filter_by(
        id=plan_id, company_id=current_user.company_id
    ).first_or_404()

    patient = plan.patient
    if patient.company_id != current_user.company_id:
        abort(403)

    try:
        pdf_buffer = generate_medication_plan_pdf(patient, plan)
        return send_file(
            pdf_buffer,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=f"{patient.full_name.replace(' ', '_')}_Medikationsplan_{datetime.now().strftime('%Y%m%d')}.pdf"
        )
    except Exception as e:
        current_app.logger.error(f"PDF generation error: {str(e)}")
        abort(500)


@export_bp.route('/leistungsnachweis/<patient_id>.pdf')
@login_required
def leistungsnachweis_pdf(patient_id):
    """Monatlicher Leistungsnachweis als PDF (für Krankenkasse)."""
    patient = Patient.query.filter_by(
        id=patient_id, company_id=current_user.company_id, deleted_at=None
    ).first_or_404()

    monat = request.args.get('monat', date.today().strftime('%Y-%m'))
    try:
        year, month = int(monat[:4]), int(monat[5:])
    except (ValueError, IndexError):
        abort(400)

    _, last_day = monthrange(year, month)
    von = date(year, month, 1)
    bis = date(year, month, last_day)

    lns = Leistungsnachweis.query.filter(
        Leistungsnachweis.patient_id == patient_id,
        Leistungsnachweis.durchgefuehrt_am >= von,
        Leistungsnachweis.durchgefuehrt_am <= bis,
    ).order_by(
        Leistungsnachweis.durchgefuehrt_am,
        Leistungsnachweis.durchgefuehrt_um,
    ).all()

    company = Company.query.get(current_user.company_id)

    try:
        buf = generate_leistungsnachweis_pdf(patient, lns, monat, company)
        filename = (
            f"Leistungsnachweis_{patient.full_name.replace(' ', '_')}_{monat}.pdf"
        )
        return send_file(buf, mimetype='application/pdf',
                         as_attachment=False, download_name=filename)
    except Exception as e:
        current_app.logger.error(f'Leistungsnachweis PDF error: {e}')
        abort(500)
