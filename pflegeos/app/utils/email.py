from flask import render_template, current_app
from flask_mail import Message
from app.extensions import mail
import logging

logger = logging.getLogger(__name__)


def send_patient_admission_email(employee_email, employee_name, patient_name, patient_id, admission_date, pflegegrad=None):
    """Send patient admission notification email."""
    try:
        system_url = current_app.config.get('SYSTEM_URL', 'http://localhost:5000')
        html = render_template('emails/patient_admission.html',
                             employee_name=employee_name,
                             patient_name=patient_name,
                             patient_id=patient_id,
                             admission_date=admission_date,
                             pflegegrad=pflegegrad,
                             system_url=system_url)

        msg = Message(
            subject=f'✓ Neuer Patient aufgenommen: {patient_name}',
            recipients=[employee_email],
            html=html,
            sender=current_app.config.get('MAIL_DEFAULT_SENDER', 'noreply@pflegeos.local')
        )
        mail.send(msg)
        logger.info(f"Patient admission email sent to {employee_email} for patient {patient_name}")
        return True
    except Exception as e:
        logger.error(f"Failed to send patient admission email: {str(e)}")
        return False


def send_missing_documentation_alert(employee_email, employee_name, missing_docs):
    """Send alert for missing critical documentation.

    missing_docs format: [
        {'patient_name': 'John Doe', 'pflegegrad': 2, 'missing': ['SIS-Einschätzung', 'Wunddokumentation']},
        ...
    ]
    """
    try:
        system_url = current_app.config.get('SYSTEM_URL', 'http://localhost:5000')
        html = render_template('emails/missing_documentation.html',
                             employee_name=employee_name,
                             missing_docs=missing_docs,
                             system_url=system_url)

        msg = Message(
            subject='⚠️ Fehlende Dokumentation erkannt',
            recipients=[employee_email],
            html=html,
            sender=current_app.config.get('MAIL_DEFAULT_SENDER', 'noreply@pflegeos.local')
        )
        mail.send(msg)
        logger.info(f"Missing documentation alert sent to {employee_email}")
        return True
    except Exception as e:
        logger.error(f"Failed to send missing documentation alert: {str(e)}")
        return False


def send_btm_alert_email(employee_email, employee_name, pending_entries):
    """Send BtM documentation alert.

    pending_entries format: [
        {'medication_name': 'Morphin 10mg', 'patient_name': 'John Doe', 'time': '14:30'},
        ...
    ]
    """
    try:
        system_url = current_app.config.get('SYSTEM_URL', 'http://localhost:5000')
        html = render_template('emails/btm_alert.html',
                             employee_name=employee_name,
                             pending_entries=pending_entries,
                             system_url=system_url)

        msg = Message(
            subject='⚠️ BtM-Dokumentation erforderlich',
            recipients=[employee_email],
            html=html,
            sender=current_app.config.get('MAIL_DEFAULT_SENDER', 'noreply@pflegeos.local')
        )
        mail.send(msg)
        logger.info(f"BtM alert email sent to {employee_email}")
        return True
    except Exception as e:
        logger.error(f"Failed to send BtM alert email: {str(e)}")
        return False


def send_bulk_missing_documentation_alerts(company_id):
    """Send missing documentation alerts to all employees in a company."""
    from app.models import Employee, Patient, SisAssessment, WoundDoc
    from datetime import date

    try:
        # Get all employees in company
        employees = Employee.query.filter_by(company_id=company_id, deleted_at=None).all()

        for employee in employees:
            # Get missing docs for this employee's patients (or company-wide depending on permissions)
            missing_docs = []
            patients = Patient.query.filter_by(company_id=company_id, status='AKTIV', deleted_at=None).all()

            for patient in patients:
                missing = []

                # Check SIS assessment
                sis = SisAssessment.query.filter_by(patient_id=patient.id, deleted_at=None).first()
                if not sis:
                    missing.append('SIS-Einschätzung')

                # Check wound documentation for high-risk patients
                if patient.dekubitus_risiko or patient.sturzrisiko:
                    wound_doc = WoundDoc.query.filter_by(patient_id=patient.id, deleted_at=None).first()
                    if not wound_doc:
                        missing.append('Wunddokumentation')

                if missing:
                    missing_docs.append({
                        'patient_name': f"{patient.vorname} {patient.nachname}",
                        'pflegegrad': patient.pflegegrad,
                        'missing': missing
                    })

            # Send alert if there are missing docs
            if missing_docs and employee.email:
                send_missing_documentation_alert(
                    employee.email,
                    employee.full_name,
                    missing_docs
                )

        logger.info(f"Bulk missing documentation alerts sent for company {company_id}")
        return True
    except Exception as e:
        logger.error(f"Failed to send bulk alerts: {str(e)}")
        return False
