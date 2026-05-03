from flask import Blueprint, send_file, abort, current_app
from flask_login import login_required, current_user
from app.models import Patient, SisAssessment, MedicationPlan
from app.utils.pdf import generate_patient_summary_pdf, generate_sis_assessment_pdf, generate_medication_plan_pdf
from datetime import datetime

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
