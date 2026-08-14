import json
import os
import threading
from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app, jsonify, abort
from flask_login import login_required, current_user
from app.extensions import db
from app.models import WoundDoc, WoundAssessment, Patient
from app.utils.auth import log_action, save_upload
from datetime import datetime, date

wounds_bp = Blueprint('wounds', __name__)


@wounds_bp.route('/patient/<patient_id>')
@login_required
def patient_list(patient_id):
    p = _get_patient(patient_id)
    wounds = WoundDoc.query.filter_by(
        patient_id=patient_id, company_id=current_user.company_id
    ).order_by(WoundDoc.is_active.desc(), WoundDoc.erstfeststellung.desc()).all()
    return render_template('wounds/list.html', patient=p, wounds=wounds)


@wounds_bp.route('/patient/<patient_id>/new', methods=['GET', 'POST'])
@login_required
def new_wound(patient_id):
    p = _get_patient(patient_id)

    if request.method == 'POST':
        fd = request.form
        bezeichnung = fd.get('wunde_bezeichnung', '').strip()
        if not bezeichnung:
            flash('Bezeichnung ist ein Pflichtfeld.', 'danger')
            return render_template('wounds/new_wound.html', patient=p)
        wound = WoundDoc(
            company_id=current_user.company_id,
            patient_id=patient_id,
            created_by=current_user.id,
            wunde_bezeichnung=bezeichnung,
            lokalisation=fd.get('lokalisation', '').strip(),
            stage=fd.get('stage', '').strip() or None,
            erstfeststellung=_parse_date(fd.get('erstfeststellung')) or date.today(),
            ursache=fd.get('ursache', '').strip(),
        )
        db.session.add(wound)
        db.session.commit()
        log_action('CREATE', 'wound_docs', entity_id=wound.id)
        flash('Wunde angelegt.', 'success')
        return redirect(url_for('wounds.new_assessment', wound_id=wound.id))

    return render_template('wounds/new_wound.html', patient=p)


@wounds_bp.route('/<wound_id>/assess', methods=['GET', 'POST'])
@login_required
def new_assessment(wound_id):
    wound = _get_wound(wound_id)
    p = wound.patient

    if request.method == 'POST':
        fd = request.form

        # Обработка фото
        foto_paths = []
        if p.einwilligung_foto:  # Только если есть согласие
            files = request.files.getlist('fotos')
            for f in files:
                if f and f.filename:
                    path = save_upload(f, subfolder=f'wounds/{wound_id}')
                    if path:
                        foto_paths.append(path)

        # Вычисляем тенденцию относительно предыдущей оценки
        tendenz = _calculate_tendenz(wound_id, fd)

        assessment = WoundAssessment(
            wound_id=wound_id,
            assessed_by=current_user.id,
            assessment_date=_parse_date(fd.get('datum')) or date.today(),
            assessment_time=datetime.utcnow().time(),
            groesse_laenge_cm=_float(fd.get('laenge')),
            groesse_breite_cm=_float(fd.get('breite')),
            tiefe_cm=_float(fd.get('tiefe')),
            stage=fd.get('stage', '').strip() or None,
            wundgrund=fd.get('wundgrund', '').strip(),
            wundrand=fd.get('wundrand', '').strip(),
            exsudat_menge=fd.get('exsudat_menge', '').strip(),
            exsudat_art=fd.get('exsudat_art', '').strip(),
            geruch=fd.get('geruch', '').strip(),
            foto_paths=json.dumps(foto_paths),
            wundauflage=fd.get('wundauflage', '').strip(),
            wundspuelung=fd.get('wundspuelung', '').strip(),
            verbandwechsel_interval=fd.get('intervall', '').strip(),
            bemerkungen=fd.get('bemerkungen', '').strip(),
            tendenz=tendenz,
            verification_method='PIN_MAC_GPS',
            device_mac=fd.get('device_mac', '').strip() or None,
            geo_lat=_float(fd.get('geo_lat')),
            geo_lng=_float(fd.get('geo_lng')),
            status='COMPLETED',
        )
        db.session.add(assessment)
        db.session.commit()
        log_action('CREATE', 'wound_assessments', entity_id=assessment.id)

        # KI-Analyse asynchron starten (nur wenn Fotos vorhanden)
        if foto_paths and current_app.config.get('ANTHROPIC_API_KEY'):
            _trigger_ai_analysis(assessment.id, current_app._get_current_object())

        flash('Wundbefund gespeichert.', 'success')
        if foto_paths and current_app.config.get('ANTHROPIC_API_KEY'):
            flash('KI-Analyse läuft im Hintergrund und wird in Kürze angezeigt.', 'info')
        return redirect(url_for('wounds.show_wound', wound_id=wound_id))

    return render_template('wounds/assessment_form.html', wound=wound, patient=p)


@wounds_bp.route('/<wound_id>')
@login_required
def show_wound(wound_id):
    wound = _get_wound(wound_id)
    assessments = WoundAssessment.query.filter_by(wound_id=wound_id).order_by(
        WoundAssessment.assessment_date.desc()).all()

    # Загружаем пути к фото
    for a in assessments:
        try:
            a.foto_list = json.loads(a.foto_paths) if a.foto_paths else []
        except Exception:
            a.foto_list = []

    return render_template('wounds/show.html', wound=wound, patient=wound.patient,
                           assessments=assessments)


def _trigger_ai_analysis(assessment_id: str, app):
    """Startet KI-Wundanalyse in einem Daemon-Thread (non-blocking)."""
    from app.services.wound_analysis_service import run_analysis_and_save

    def _run():
        run_analysis_and_save(assessment_id, app=app)

    t = threading.Thread(target=_run, daemon=True)
    t.start()


@wounds_bp.route('/assessment/<assessment_id>/ai-analyse', methods=['POST'])
@login_required
def trigger_ai_analyse(assessment_id):
    """Manueller Neustart der KI-Analyse (AJAX-Endpunkt)."""
    a = WoundAssessment.query.join(WoundDoc).filter(
        WoundAssessment.id == assessment_id,
        WoundDoc.company_id == current_user.company_id,
    ).first_or_404()

    if not current_app.config.get('ANTHROPIC_API_KEY'):
        return jsonify({'error': 'KI-Analyse nicht konfiguriert.'}), 503

    # Vorherige Analyse löschen, damit sie neu läuft
    a.foto_ai_analysis = None
    db.session.commit()

    _trigger_ai_analysis(a.id, current_app._get_current_object())
    return jsonify({'status': 'started', 'assessment_id': assessment_id})


@wounds_bp.route('/assessment/<assessment_id>/ai-result')
@login_required
def ai_result(assessment_id):
    """Gibt aktuelles KI-Analyse-Ergebnis zurück (Polling-Endpunkt)."""
    a = WoundAssessment.query.join(WoundDoc).filter(
        WoundAssessment.id == assessment_id,
        WoundDoc.company_id == current_user.company_id,
    ).first_or_404()

    if not a.foto_ai_analysis:
        return jsonify({'status': 'pending'})

    try:
        data = json.loads(a.foto_ai_analysis)
        return jsonify({'status': 'ready', 'data': data})
    except Exception:
        return jsonify({'status': 'error'})


def _calculate_tendenz(wound_id, fd):
    """Сравнивает с последней оценкой для определения тенденции."""
    last = WoundAssessment.query.filter_by(wound_id=wound_id).order_by(
        WoundAssessment.assessment_date.desc()).first()
    if not last:
        return None
    try:
        new_area = (float(fd.get('laenge') or 0)) * (float(fd.get('breite') or 0))
        old_area = (last.groesse_laenge_cm or 0) * (last.groesse_breite_cm or 0)
        if new_area < old_area * 0.9:
            return 'Verbesserung'
        elif new_area > old_area * 1.1:
            return 'Verschlechterung'
        else:
            return 'Stagnation'
    except Exception:
        return None


def _get_patient(patient_id):
    return Patient.query.filter_by(id=patient_id,
                                   company_id=current_user.company_id,
                                   deleted_at=None).first_or_404()


def _get_wound(wound_id):
    return WoundDoc.query.filter_by(id=wound_id,
                                    company_id=current_user.company_id).first_or_404()


def _parse_date(value):
    if not value:
        return None
    try:
        return datetime.strptime(value, '%Y-%m-%d').date()
    except Exception:
        return None


def _float(val):
    try:
        return float(val) if val is not None and val != '' else None
    except Exception:
        return None
