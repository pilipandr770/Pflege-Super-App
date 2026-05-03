from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app.extensions import db
from app.models import Leistungsnachweis, Leistungskatalog, Patient
from app.utils.auth import log_action
from datetime import datetime, date, time as dtime

leistung_bp = Blueprint('leistung', __name__)


@leistung_bp.route('/patient/<patient_id>')
@login_required
def patient_list(patient_id):
    p = _get_patient(patient_id)
    month = request.args.get('month', date.today().strftime('%Y-%m'))
    try:
        year, mon = map(int, month.split('-'))
        from calendar import monthrange
        days = monthrange(year, mon)[1]
        start = date(year, mon, 1)
        end = date(year, mon, days)
    except Exception:
        start = end = date.today()

    nachweise = Leistungsnachweis.query.filter(
        Leistungsnachweis.patient_id == patient_id,
        Leistungsnachweis.durchgefuehrt_am >= start,
        Leistungsnachweis.durchgefuehrt_am <= end,
    ).order_by(Leistungsnachweis.durchgefuehrt_am.desc(),
               Leistungsnachweis.durchgefuehrt_um.desc()).all()

    return render_template('leistung/list.html', patient=p,
                           nachweise=nachweise, month=month)


@leistung_bp.route('/new', methods=['GET', 'POST'])
@login_required
def new():
    patient_id = request.args.get('patient_id') or request.form.get('patient_id')
    p = _get_patient(patient_id) if patient_id else None

    katalog = Leistungskatalog.query.filter_by(
        company_id=current_user.company_id, is_active=True
    ).order_by(Leistungskatalog.kategorie, Leistungskatalog.bezeichnung).all()

    if request.method == 'POST':
        fd = request.form
        leistung_id = fd.get('leistung_id')
        if not leistung_id or not patient_id:
            flash('Bitte Patient und Leistung auswählen.', 'danger')
            return redirect(request.url)

        nachweis = Leistungsnachweis(
            company_id=current_user.company_id,
            patient_id=patient_id,
            employee_id=current_user.id,
            leistung_id=leistung_id,
            durchgefuehrt_am=_parse_date(fd.get('datum')) or date.today(),
            durchgefuehrt_um=_parse_time(fd.get('uhrzeit')) or datetime.utcnow().time(),
            dauer_minuten=int(fd['dauer']) if fd.get('dauer') else None,
            verification_method=fd.get('verification_method', 'MAC_GPS'),
            device_mac=fd.get('device_mac', '').strip() or None,
            geo_lat=_float(fd.get('geo_lat')),
            geo_lng=_float(fd.get('geo_lng')),
            nfc_tag_id=fd.get('nfc_tag_id', '').strip() or None,
            bemerkungen=fd.get('bemerkungen', '').strip(),
        )
        db.session.add(nachweis)
        db.session.commit()
        log_action('CREATE', 'leistungsnachweise', entity_id=nachweis.id)
        flash('Leistung dokumentiert.', 'success')
        return redirect(url_for('leistung.patient_list', patient_id=patient_id))

    patients = Patient.query.filter_by(
        company_id=current_user.company_id, status='AKTIV', deleted_at=None
    ).order_by(Patient.nachname).all()

    return render_template('leistung/form.html',
                           patient=p, patients=patients,
                           katalog=katalog, today=date.today())


@leistung_bp.route('/katalog', methods=['GET', 'POST'])
@login_required
def katalog_manage():
    if not current_user.is_admin:
        flash('Keine Berechtigung.', 'danger')
        return redirect(url_for('dashboard.index'))

    if request.method == 'POST':
        fd = request.form
        item = Leistungskatalog(
            company_id=current_user.company_id,
            leistung_nr=fd.get('leistung_nr', '').strip(),
            bezeichnung=fd.get('bezeichnung', '').strip(),
            beschreibung=fd.get('beschreibung', '').strip(),
            kategorie=fd.get('kategorie', '').strip(),
            dauer_minuten=int(fd['dauer_minuten']) if fd.get('dauer_minuten') else None,
            preis=float(fd['preis']) if fd.get('preis') else None,
        )
        db.session.add(item)
        db.session.commit()
        flash('Leistung hinzugefügt.', 'success')
        return redirect(url_for('leistung.katalog_manage'))

    items = Leistungskatalog.query.filter_by(
        company_id=current_user.company_id
    ).order_by(Leistungskatalog.kategorie).all()
    return render_template('leistung/katalog.html', items=items)


def _get_patient(patient_id):
    return Patient.query.filter_by(id=patient_id,
                                   company_id=current_user.company_id,
                                   deleted_at=None).first_or_404()


def _parse_date(value):
    if not value:
        return None
    try:
        return datetime.strptime(value, '%Y-%m-%d').date()
    except Exception:
        return None


def _parse_time(value):
    if not value:
        return None
    try:
        return datetime.strptime(value, '%H:%M').time()
    except Exception:
        return None


def _float(val):
    try:
        return float(val) if val is not None and val != '' else None
    except Exception:
        return None
