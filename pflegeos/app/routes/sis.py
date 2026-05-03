from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app.extensions import db
from app.models import SisAssessment, Patient
from app.utils.auth import log_action
from datetime import date, timedelta

sis_bp = Blueprint('sis', __name__)

SCORE_LABELS = {
    0: 'Selbständig',
    1: 'Überwiegend selbständig',
    2: 'Überwiegend unselbständig',
    3: 'Unselbständig'
}


@sis_bp.route('/patient/<patient_id>')
@login_required
def patient_list(patient_id):
    p = _get_patient(patient_id)
    assessments = SisAssessment.query.filter_by(patient_id=patient_id).order_by(
        SisAssessment.assessment_date.desc()).all()
    return render_template('sis/list.html', patient=p, assessments=assessments,
                           score_labels=SCORE_LABELS)


@sis_bp.route('/patient/<patient_id>/new', methods=['GET', 'POST'])
@login_required
def new(patient_id):
    p = _get_patient(patient_id)
    errors = {}

    if request.method == 'POST':
        fd = request.form

        # Деактивируем предыдущую версию
        SisAssessment.query.filter_by(patient_id=patient_id, is_current=True).update({'is_current': False})

        # Получаем последний номер версии
        last = SisAssessment.query.filter_by(patient_id=patient_id).order_by(
            SisAssessment.version.desc()).first()
        new_version = (last.version + 1) if last else 1

        sis = SisAssessment(
            company_id=current_user.company_id,
            patient_id=patient_id,
            created_by=current_user.id,
            version=new_version,
            is_current=True,

            kb1_orientierung=_int(fd.get('kb1_orientierung')),
            kb1_gedaechtnis=_int(fd.get('kb1_gedaechtnis')),
            kb1_verstehen=_int(fd.get('kb1_verstehen')),
            kb1_kommunikation=_int(fd.get('kb1_kommunikation')),
            kb1_verhalten=_int(fd.get('kb1_verhalten')),
            kb1_freitext=fd.get('kb1_freitext', '').strip(),

            kb2_positionswechsel=_int(fd.get('kb2_positionswechsel')),
            kb2_transfer=_int(fd.get('kb2_transfer')),
            kb2_gehen=_int(fd.get('kb2_gehen')),
            kb2_treppensteigen=_int(fd.get('kb2_treppensteigen')),
            kb2_hilfsmittel=fd.get('kb2_hilfsmittel', '').strip(),
            kb2_freitext=fd.get('kb2_freitext', '').strip(),

            kb3_medikamente=fd.get('kb3_medikamente', '').strip(),
            kb3_injektionen='kb3_injektionen' in fd,
            kb3_verbandwechsel='kb3_verbandwechsel' in fd,
            kb3_katheter='kb3_katheter' in fd,
            kb3_sonde='kb3_sonde' in fd,
            kb3_sauerstoff='kb3_sauerstoff' in fd,
            kb3_freitext=fd.get('kb3_freitext', '').strip(),

            kb4_koerperpflege=_int(fd.get('kb4_koerperpflege')),
            kb4_ernaehrung=_int(fd.get('kb4_ernaehrung')),
            kb4_trinken=_int(fd.get('kb4_trinken')),
            kb4_ausscheidung=_int(fd.get('kb4_ausscheidung')),
            kb4_ankleiden=_int(fd.get('kb4_ankleiden')),
            kb4_kostform=fd.get('kb4_kostform', '').strip(),
            kb4_freitext=fd.get('kb4_freitext', '').strip(),

            kb5_soziale_kontakte=fd.get('kb5_soziale_kontakte', '').strip(),
            kb5_tagesstruktur=fd.get('kb5_tagesstruktur', '').strip(),
            kb5_interessen=fd.get('kb5_interessen', '').strip(),
            kb5_freitext=fd.get('kb5_freitext', '').strip(),

            pflegeschwerpunkte=fd.get('pflegeschwerpunkte', '').strip(),
            ziele=fd.get('ziele', '').strip(),
            besonderheiten=fd.get('besonderheiten', '').strip(),

            verification_method='PIN_MAC_GPS',
            device_mac=fd.get('device_mac', '').strip() or None,
            geo_lat=_float(fd.get('geo_lat')),
            geo_lng=_float(fd.get('geo_lng')),

            status='COMPLETED',
            assessment_date=date.today(),
            next_review_date=date.today() + timedelta(days=180),
        )
        db.session.add(sis)
        db.session.commit()
        log_action('CREATE', 'sis_assessments', entity_id=sis.id)
        flash('SIS erfolgreich gespeichert.', 'success')
        return redirect(url_for('sis.show', sis_id=sis.id))

    return render_template('sis/form.html', patient=p, sis=None,
                           score_labels=SCORE_LABELS, errors=errors)


@sis_bp.route('/<sis_id>')
@login_required
def show(sis_id):
    sis = _get_sis(sis_id)
    return render_template('sis/show.html', sis=sis, patient=sis.patient,
                           score_labels=SCORE_LABELS)


@sis_bp.route('/<sis_id>/approve', methods=['POST'])
@login_required
def approve(sis_id):
    if not current_user.can_approve_documents:
        flash('Keine Berechtigung.', 'danger')
        return redirect(url_for('sis.show', sis_id=sis_id))
    sis = _get_sis(sis_id)
    from datetime import datetime
    sis.approved_by = current_user.id
    sis.approved_at = datetime.utcnow()
    sis.status = 'VERIFIED'
    db.session.commit()
    log_action('APPROVE', 'sis_assessments', entity_id=sis.id)
    flash('SIS freigegeben.', 'success')
    return redirect(url_for('sis.show', sis_id=sis_id))


def _get_patient(patient_id):
    return Patient.query.filter_by(id=patient_id,
                                   company_id=current_user.company_id,
                                   deleted_at=None).first_or_404()


def _get_sis(sis_id):
    return SisAssessment.query.filter_by(id=sis_id,
                                         company_id=current_user.company_id).first_or_404()


def _int(val):
    try:
        return int(val) if val is not None and val != '' else None
    except (ValueError, TypeError):
        return None


def _float(val):
    try:
        return float(val) if val is not None and val != '' else None
    except (ValueError, TypeError):
        return None
