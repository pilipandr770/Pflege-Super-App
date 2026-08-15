from flask import Blueprint, send_file, abort, current_app, request, render_template, redirect, url_for
from flask_login import login_required, current_user
from app.models import Patient, SisAssessment, MedicationPlan, Leistungsnachweis, Company, WoundDoc, Sturzprotokoll
from app.utils.pdf import (generate_patient_summary_pdf, generate_sis_assessment_pdf,
                            generate_medication_plan_pdf, generate_leistungsnachweis_pdf)
from datetime import datetime, date, timedelta
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


# ── MDK-Prüfungspaket ─────────────────────────────────────────────────────────

@export_bp.route('/patient/<patient_id>/doku-paket', methods=['GET', 'POST'])
@login_required
def pflegedoku_paket(patient_id):
    """MDK-Prüfungspaket: kombiniertes PDF aus mehreren Dokumenten."""
    patient = Patient.query.filter_by(
        id=patient_id, company_id=current_user.company_id, deleted_at=None
    ).first_or_404()

    # Verfügbare Daten laden
    sis = (SisAssessment.query
           .filter_by(patient_id=patient_id, is_current=True)
           .order_by(SisAssessment.assessment_date.desc())
           .first())
    medplan = (MedicationPlan.query
               .filter_by(patient_id=patient_id, is_current=True)
               .order_by(MedicationPlan.valid_from.desc())
               .first())
    wounds = (WoundDoc.query
              .filter_by(patient_id=patient_id, is_active=True)
              .order_by(WoundDoc.erstfeststellung.desc())
              .all())
    since_12m = date.today() - timedelta(days=365)
    stuerze = (Sturzprotokoll.query
               .filter_by(patient_id=patient_id)
               .filter(Sturzprotokoll.sturz_datum >= since_12m)
               .order_by(Sturzprotokoll.sturz_datum.desc())
               .all())

    # Letzte 12 Monate für Monatsauswahl
    monate = []
    today = date.today()
    for i in range(12):
        d = date(today.year, today.month, 1) - timedelta(days=i * 28)
        monate.append(f'{d.year}-{d.month:02d}')

    if request.method == 'GET':
        return render_template('exports/pflegedoku_auswahl.html',
                               patient=patient,
                               sis=sis,
                               medplan=medplan,
                               wounds=wounds,
                               stuerze=stuerze,
                               monate=monate)

    # POST — PDF generieren
    fd = request.form
    include = {
        'sis':          bool(fd.get('include_sis')) and sis is not None,
        'medikamente':  bool(fd.get('include_medikamente')) and medplan is not None,
        'wunden':       bool(fd.get('include_wunden')) and bool(wounds),
        'leistungen':   bool(fd.get('include_leistungen')),
        'stuerze':      bool(fd.get('include_stuerze')) and bool(stuerze),
    }
    leistung_monat = fd.get('leistung_monat', today.strftime('%Y-%m'))

    leistungen = []
    if include['leistungen']:
        try:
            y, m = int(leistung_monat[:4]), int(leistung_monat[5:])
            _, last_day = monthrange(y, m)
            leistungen = Leistungsnachweis.query.filter(
                Leistungsnachweis.patient_id == patient_id,
                Leistungsnachweis.durchgefuehrt_am >= date(y, m, 1),
                Leistungsnachweis.durchgefuehrt_am <= date(y, m, last_day),
            ).order_by(Leistungsnachweis.durchgefuehrt_am).all()
        except (ValueError, IndexError):
            pass

    company = Company.query.get(current_user.company_id)
    try:
        from app.utils.pdf import generate_pflegedoku_paket_pdf
        buf = generate_pflegedoku_paket_pdf(
            patient, company, include,
            sis=sis, medplan=medplan, wounds=wounds,
            leistungen=leistungen, leistung_monat=leistung_monat,
            stuerze=stuerze,
        )
        fname = (f'MDK_Paket_{patient.full_name.replace(" ", "_")}_'
                 f'{date.today().strftime("%Y%m%d")}.pdf')
        return send_file(buf, mimetype='application/pdf',
                         as_attachment=True, download_name=fname)
    except Exception as e:
        current_app.logger.error(f'MDK-Paket PDF error: {e}')
        abort(500)
