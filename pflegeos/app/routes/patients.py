from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
from app.extensions import db
from app.models import Patient, Employee, EmployeePatientAssignment
from app.utils.auth import log_action, patient_access_required
from app.utils.email import send_patient_admission_email
from datetime import datetime, date

patients_bp = Blueprint('patients', __name__)


@patients_bp.route('/')
@login_required
def index():
    cid = current_user.company_id
    status_filter = request.args.get('status', 'AKTIV')
    search = request.args.get('q', '').strip()

    q = Patient.query.filter_by(company_id=cid, deleted_at=None)

    # Если пользователь не админ, показываем только назначенных пациентов
    if not current_user.is_admin:
        assigned_patient_ids = db.session.query(EmployeePatientAssignment.patient_id).filter_by(
            employee_id=current_user.id,
            is_active=True
        ).all()
        assigned_ids = [p[0] for p in assigned_patient_ids]

        if assigned_ids:
            q = q.filter(Patient.id.in_(assigned_ids))
        else:
            # Если нет назначенных пациентов, вернуть пусто
            patients = []
            return render_template('patients/index.html', patients=patients,
                                 status_filter=status_filter, search=search)

    if status_filter:
        q = q.filter_by(status=status_filter)
    if search:
        q = q.filter(
            (Patient.vorname.ilike(f'%{search}%')) |
            (Patient.nachname.ilike(f'%{search}%')) |
            (Patient.zimmer_nr.ilike(f'%{search}%'))
        )

    patients = q.order_by(Patient.nachname, Patient.vorname).all()
    return render_template('patients/index.html', patients=patients,
                           status_filter=status_filter, search=search)


@patients_bp.route('/new', methods=['GET', 'POST'])
@login_required
def new():
    errors = {}
    form_data = {}

    if request.method == 'POST':
        form_data = request.form.to_dict()
        required = ['vorname', 'nachname', 'pflegegrad', 'aufnahmedatum']
        for f in required:
            if not form_data.get(f, '').strip():
                errors[f] = 'Pflichtfeld'

        if not errors:
            p = Patient(
                company_id=current_user.company_id,
                vorname=form_data['vorname'].strip(),
                nachname=form_data['nachname'].strip(),
                geburtsdatum=_parse_date(form_data.get('geburtsdatum')),
                gender=form_data.get('gender'),
                nationalitaet=form_data.get('nationalitaet', '').strip(),
                religion=form_data.get('religion', '').strip(),
                sprache_muttersprache=form_data.get('sprache_muttersprache', '').strip(),
                betreuer_name=form_data.get('betreuer_name', '').strip(),
                betreuer_telefon=form_data.get('betreuer_telefon', '').strip(),
                betreuer_verhaeltnis=form_data.get('betreuer_verhaeltnis', '').strip(),
                betreuer_email=form_data.get('betreuer_email', '').strip(),
                portal_enabled='portal_enabled' in form_data,
                arzt_portal_enabled='arzt_portal_enabled' in form_data,
                hausarzt_name=form_data.get('hausarzt_name', '').strip(),
                hausarzt_telefon=form_data.get('hausarzt_telefon', '').strip(),
                pflegegrad=form_data.get('pflegegrad'),
                pflegegrad_seit=_parse_date(form_data.get('pflegegrad_seit')),
                care_type=form_data.get('care_type', 'HOME_CARE'),
                strasse=form_data.get('strasse', '').strip(),
                hausnummer=form_data.get('hausnummer', '').strip(),
                plz=form_data.get('plz', '').strip(),
                ort=form_data.get('ort', '').strip(),
                bundesland=form_data.get('bundesland', '').strip(),
                zimmer_nr=form_data.get('zimmer_nr', '').strip(),
                bett_nr=form_data.get('bett_nr', '').strip(),
                aufnahmedatum=_parse_date(form_data.get('aufnahmedatum')),
                krankenversicherung=form_data.get('krankenversicherung', '').strip(),
                versicherungsnummer=form_data.get('versicherungsnummer', '').strip(),
                allergien=form_data.get('allergien', '').strip(),
                gewicht_kg=float(form_data['gewicht_kg']) if form_data.get('gewicht_kg') else None,
                groesse_cm=int(form_data['groesse_cm']) if form_data.get('groesse_cm') else None,
                blutgruppe=form_data.get('blutgruppe', '').strip(),
                sturzrisiko='sturzrisiko' in form_data,
                dekubitusrisiko='dekubitusrisiko' in form_data,
                ernaehrungsrisiko='ernaehrungsrisiko' in form_data,
                einwilligung_foto='einwilligung_foto' in form_data,
                status='AKTIV',
            )
            db.session.add(p)
            db.session.commit()
            log_action('CREATE', 'patients', entity_id=p.id)

            # Send admission notification emails to employees
            employees = Employee.query.filter_by(company_id=current_user.company_id, deleted_at=None).all()
            for emp in employees:
                if emp.email:
                    send_patient_admission_email(
                        emp.email,
                        emp.full_name,
                        p.full_name,
                        p.id,
                        p.aufnahmedatum,
                        p.pflegegrad
                    )

            flash(f'Patient {p.full_name} wurde erfolgreich angelegt.', 'success')
            return redirect(url_for('patients.show', patient_id=p.id))

    return render_template('patients/form.html', errors=errors, form_data=form_data,
                           patient=None, title='Neuer Patient')


@patients_bp.route('/<patient_id>')
@login_required
@patient_access_required()
def show(patient_id):
    p = _get_patient(patient_id)
    return render_template('patients/show.html', patient=p)


@patients_bp.route('/<patient_id>/edit', methods=['GET', 'POST'])
@login_required
@patient_access_required()
def edit(patient_id):
    p = _get_patient(patient_id)
    errors = {}
    form_data = {}

    if request.method == 'POST':
        form_data = request.form.to_dict()
        p.vorname = form_data.get('vorname', '').strip()
        p.nachname = form_data.get('nachname', '').strip()
        p.geburtsdatum = _parse_date(form_data.get('geburtsdatum'))
        p.gender = form_data.get('gender')
        p.pflegegrad = form_data.get('pflegegrad')
        p.pflegegrad_seit = _parse_date(form_data.get('pflegegrad_seit'))
        p.care_type = form_data.get('care_type', 'HOME_CARE')
        p.strasse = form_data.get('strasse', '').strip()
        p.hausnummer = form_data.get('hausnummer', '').strip()
        p.plz = form_data.get('plz', '').strip()
        p.ort = form_data.get('ort', '').strip()
        p.bundesland = form_data.get('bundesland', '').strip()
        p.zimmer_nr = form_data.get('zimmer_nr', '').strip()
        p.bett_nr = form_data.get('bett_nr', '').strip()
        p.betreuer_name = form_data.get('betreuer_name', '').strip()
        p.betreuer_telefon = form_data.get('betreuer_telefon', '').strip()
        p.betreuer_email = form_data.get('betreuer_email', '').strip()
        p.portal_enabled = 'portal_enabled' in form_data
        p.arzt_portal_enabled = 'arzt_portal_enabled' in form_data
        p.hausarzt_name = form_data.get('hausarzt_name', '').strip()
        p.hausarzt_telefon = form_data.get('hausarzt_telefon', '').strip()
        p.allergien = form_data.get('allergien', '').strip()
        p.sturzrisiko = 'sturzrisiko' in form_data
        p.dekubitusrisiko = 'dekubitusrisiko' in form_data
        p.ernaehrungsrisiko = 'ernaehrungsrisiko' in form_data
        p.einwilligung_foto = 'einwilligung_foto' in form_data
        p.status = form_data.get('status', 'AKTIV')
        db.session.commit()
        log_action('UPDATE', 'patients', entity_id=p.id)
        flash('Patientendaten aktualisiert.', 'success')
        return redirect(url_for('patients.show', patient_id=p.id))

    form_data = {
        'vorname': p.vorname, 'nachname': p.nachname,
        'geburtsdatum': p.geburtsdatum.strftime('%Y-%m-%d') if p.geburtsdatum else '',
        'gender': p.gender, 'pflegegrad': p.pflegegrad,
        'pflegegrad_seit': p.pflegegrad_seit.strftime('%Y-%m-%d') if p.pflegegrad_seit else '',
        'care_type': p.care_type or 'HOME_CARE',
        'strasse': p.strasse or '', 'hausnummer': p.hausnummer or '',
        'plz': p.plz or '', 'ort': p.ort or '', 'bundesland': p.bundesland or '',
        'zimmer_nr': p.zimmer_nr or '', 'bett_nr': p.bett_nr or '',
        'betreuer_name': p.betreuer_name or '', 'betreuer_telefon': p.betreuer_telefon or '',
        'betreuer_email': p.betreuer_email or '', 'portal_enabled': p.portal_enabled,
        'arzt_portal_enabled': p.arzt_portal_enabled,
        'hausarzt_name': p.hausarzt_name or '', 'hausarzt_telefon': p.hausarzt_telefon or '',
        'allergien': p.allergien or '', 'status': p.status,
        'sturzrisiko': p.sturzrisiko, 'dekubitusrisiko': p.dekubitusrisiko,
        'ernaehrungsrisiko': p.ernaehrungsrisiko, 'einwilligung_foto': p.einwilligung_foto,
    }

    return render_template('patients/form.html', errors=errors, form_data=form_data,
                           patient=p, title=f'{p.full_name} bearbeiten')


def _get_patient(patient_id):
    p = Patient.query.filter_by(id=patient_id,
                                company_id=current_user.company_id,
                                deleted_at=None).first_or_404()
    return p


def _parse_date(value):
    if not value:
        return None
    try:
        return datetime.strptime(value, '%Y-%m-%d').date()
    except (ValueError, TypeError):
        return None


# ── Portal-Toggles ────────────────────────────────────────────────────────────

@patients_bp.route('/<patient_id>/toggle-portal', methods=['POST'])
@login_required
def toggle_portal(patient_id):
    from app.utils.auth import admin_required as _ar
    if not current_user.is_admin:
        abort(403)
    p = _get_patient(patient_id)
    p.portal_enabled = not p.portal_enabled
    db.session.commit()
    action = 'PORTAL_ENABLED' if p.portal_enabled else 'PORTAL_DISABLED'
    log_action(action, 'Patient', patient_id)
    state = 'aktiviert' if p.portal_enabled else 'deaktiviert'
    flash(f'Angehörigen-Portal {state}.', 'success')
    return redirect(url_for('patients.show', patient_id=patient_id))


@patients_bp.route('/<patient_id>/toggle-arzt-portal', methods=['POST'])
@login_required
def toggle_arzt_portal(patient_id):
    if not current_user.is_admin:
        abort(403)
    p = _get_patient(patient_id)
    p.arzt_portal_enabled = not p.arzt_portal_enabled
    db.session.commit()
    action = 'ARZT_PORTAL_ENABLED' if p.arzt_portal_enabled else 'ARZT_PORTAL_DISABLED'
    log_action(action, 'Patient', patient_id)
    state = 'aktiviert' if p.arzt_portal_enabled else 'deaktiviert'
    flash(f'Hausarzt-Portal {state}.', 'success')
    return redirect(url_for('patients.show', patient_id=patient_id))
