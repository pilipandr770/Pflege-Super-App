"""
Fuhrpark — Fahrzeugflotten-Verwaltung für ambulante Pflegedienste.
Admin: volle Verwaltung (Kartei, Berichte, Schäden)
FAHRER: eigene Fahrten eintragen + Schäden melden
"""
from flask import (Blueprint, render_template, request, redirect,
                   url_for, flash, abort, jsonify)
from flask_login import login_required, current_user
from app.extensions import db
from app.models import Fahrzeug, Kilometerbuch, Schadensmeldung, Employee, Patient
from app.utils.auth import admin_required, log_action
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation

fuhrpark_bp = Blueprint('fuhrpark', __name__, url_prefix='/fuhrpark')


def _can_access():
    """Admin oder FAHRER."""
    if not current_user.is_authenticated:
        abort(403)
    if current_user.is_admin or current_user.role == 'FAHRER':
        return True
    abort(403)


def _parse_date(val):
    if not val:
        return None
    try:
        return datetime.strptime(val, '%Y-%m-%d').date()
    except (ValueError, TypeError):
        return None


def _parse_int(val):
    try:
        return int(val) if val else None
    except (ValueError, TypeError):
        return None


def _parse_decimal(val):
    try:
        return Decimal(val) if val else None
    except (ValueError, InvalidOperation):
        return None


# ─────────────────────────────────────────────────────────────
# FAHRZEUG-LISTE
# ─────────────────────────────────────────────────────────────

@fuhrpark_bp.route('/')
@login_required
def index():
    _can_access()
    cid = current_user.company_id

    fahrzeuge = Fahrzeug.query.filter_by(
        company_id=cid, deleted_at=None
    ).order_by(Fahrzeug.kennzeichen).all()

    # Alerts: Fahrzeuge mit ablaufenden Dokumenten
    alerts = [f for f in fahrzeuge if f.hat_alerts and f.status == 'AKTIV']

    # Stats
    aktiv     = sum(1 for f in fahrzeuge if f.status == 'AKTIV')
    werkstatt = sum(1 for f in fahrzeuge if f.status == 'WERKSTATT')

    return render_template('fuhrpark/index.html',
                           fahrzeuge=fahrzeuge,
                           alerts=alerts,
                           aktiv=aktiv,
                           werkstatt=werkstatt)


# ─────────────────────────────────────────────────────────────
# FAHRZEUG ANLEGEN / BEARBEITEN
# ─────────────────────────────────────────────────────────────

@fuhrpark_bp.route('/neu', methods=['GET', 'POST'])
@login_required
@admin_required
def neu():
    errors = {}
    form_data = {}

    if request.method == 'POST':
        form_data = request.form.to_dict()
        if not form_data.get('kennzeichen', '').strip():
            errors['kennzeichen'] = 'Pflichtfeld'

        if not errors:
            f = Fahrzeug(
                company_id=current_user.company_id,
                kennzeichen=form_data['kennzeichen'].strip().upper(),
                marke=form_data.get('marke', '').strip(),
                modell=form_data.get('modell', '').strip(),
                baujahr=_parse_int(form_data.get('baujahr')),
                farbe=form_data.get('farbe', '').strip(),
                kraftstoff=form_data.get('kraftstoff', 'Diesel'),
                fahrgestellnummer=form_data.get('fahrgestellnummer', '').strip(),
                tuev_bis=_parse_date(form_data.get('tuev_bis')),
                versicherung_bis=_parse_date(form_data.get('versicherung_bis')),
                versicherung_nr=form_data.get('versicherung_nr', '').strip(),
                versicherung_gesellschaft=form_data.get('versicherung_gesellschaft', '').strip(),
                km_stand=_parse_int(form_data.get('km_stand')),
                km_stand_datum=_parse_date(form_data.get('km_stand_datum')),
                anschaffungsdatum=_parse_date(form_data.get('anschaffungsdatum')),
                status=form_data.get('status', 'AKTIV'),
                notizen=form_data.get('notizen', '').strip(),
            )
            db.session.add(f)
            db.session.commit()
            log_action('CREATE', 'Fahrzeug', f.id)
            flash(f'✓ Fahrzeug {f.kennzeichen} wurde angelegt.', 'success')
            return redirect(url_for('fuhrpark.detail', fahrzeug_id=f.id))

    return render_template('fuhrpark/form.html',
                           fahrzeug=None, form_data=form_data,
                           errors=errors, title='Neues Fahrzeug')


@fuhrpark_bp.route('/<fahrzeug_id>/bearbeiten', methods=['GET', 'POST'])
@login_required
@admin_required
def bearbeiten(fahrzeug_id):
    f = Fahrzeug.query.filter_by(
        id=fahrzeug_id, company_id=current_user.company_id, deleted_at=None
    ).first_or_404()

    errors = {}
    form_data = {}

    if request.method == 'POST':
        form_data = request.form.to_dict()
        if not form_data.get('kennzeichen', '').strip():
            errors['kennzeichen'] = 'Pflichtfeld'

        if not errors:
            f.kennzeichen           = form_data['kennzeichen'].strip().upper()
            f.marke                 = form_data.get('marke', '').strip()
            f.modell                = form_data.get('modell', '').strip()
            f.baujahr               = _parse_int(form_data.get('baujahr'))
            f.farbe                 = form_data.get('farbe', '').strip()
            f.kraftstoff            = form_data.get('kraftstoff', 'Diesel')
            f.fahrgestellnummer     = form_data.get('fahrgestellnummer', '').strip()
            f.tuev_bis              = _parse_date(form_data.get('tuev_bis'))
            f.versicherung_bis      = _parse_date(form_data.get('versicherung_bis'))
            f.versicherung_nr       = form_data.get('versicherung_nr', '').strip()
            f.versicherung_gesellschaft = form_data.get('versicherung_gesellschaft', '').strip()
            f.km_stand              = _parse_int(form_data.get('km_stand'))
            f.km_stand_datum        = _parse_date(form_data.get('km_stand_datum'))
            f.anschaffungsdatum     = _parse_date(form_data.get('anschaffungsdatum'))
            f.status                = form_data.get('status', 'AKTIV')
            f.notizen               = form_data.get('notizen', '').strip()
            f.updated_at            = datetime.utcnow()
            db.session.commit()
            log_action('UPDATE', 'Fahrzeug', f.id)
            flash(f'✓ Fahrzeug {f.kennzeichen} aktualisiert.', 'success')
            return redirect(url_for('fuhrpark.detail', fahrzeug_id=f.id))

    form_data = {
        'kennzeichen': f.kennzeichen, 'marke': f.marke or '',
        'modell': f.modell or '', 'baujahr': f.baujahr or '',
        'farbe': f.farbe or '', 'kraftstoff': f.kraftstoff or 'Diesel',
        'fahrgestellnummer': f.fahrgestellnummer or '',
        'tuev_bis': f.tuev_bis.strftime('%Y-%m-%d') if f.tuev_bis else '',
        'versicherung_bis': f.versicherung_bis.strftime('%Y-%m-%d') if f.versicherung_bis else '',
        'versicherung_nr': f.versicherung_nr or '',
        'versicherung_gesellschaft': f.versicherung_gesellschaft or '',
        'km_stand': f.km_stand or '', 'km_stand_datum': f.km_stand_datum.strftime('%Y-%m-%d') if f.km_stand_datum else '',
        'anschaffungsdatum': f.anschaffungsdatum.strftime('%Y-%m-%d') if f.anschaffungsdatum else '',
        'status': f.status, 'notizen': f.notizen or '',
    }

    return render_template('fuhrpark/form.html',
                           fahrzeug=f, form_data=form_data,
                           errors=errors, title=f'{f.kennzeichen} bearbeiten')


# ─────────────────────────────────────────────────────────────
# FAHRZEUG DETAIL
# ─────────────────────────────────────────────────────────────

@fuhrpark_bp.route('/<fahrzeug_id>')
@login_required
def detail(fahrzeug_id):
    _can_access()
    f = Fahrzeug.query.filter_by(
        id=fahrzeug_id, company_id=current_user.company_id, deleted_at=None
    ).first_or_404()

    # Letzte 30 Fahrten
    fahrten = Kilometerbuch.query.filter_by(fahrzeug_id=f.id)\
        .order_by(Kilometerbuch.datum.desc(), Kilometerbuch.created_at.desc())\
        .limit(50).all()

    # Offene Schäden
    schaeden = Schadensmeldung.query.filter_by(
        fahrzeug_id=f.id
    ).order_by(Schadensmeldung.datum.desc()).all()

    # Monat-Stats
    erster = date.today().replace(day=1)
    km_monat = sum(
        e.km_gesamt for e in Kilometerbuch.query.filter(
            Kilometerbuch.fahrzeug_id == f.id,
            Kilometerbuch.datum >= erster
        ).all()
    )

    return render_template('fuhrpark/detail.html',
                           fahrzeug=f,
                           fahrten=fahrten,
                           schaeden=schaeden,
                           km_monat=km_monat,
                           heute=date.today())


# ─────────────────────────────────────────────────────────────
# KILOMETERBUCH EINTRAG
# ─────────────────────────────────────────────────────────────

@fuhrpark_bp.route('/km/neu', methods=['GET', 'POST'])
@fuhrpark_bp.route('/<fahrzeug_id>/km/neu', methods=['GET', 'POST'])
@login_required
def km_neu(fahrzeug_id=None):
    _can_access()
    cid = current_user.company_id

    # Fahrzeuge für Select
    fahrzeuge = Fahrzeug.query.filter_by(
        company_id=cid, deleted_at=None, status='AKTIV'
    ).order_by(Fahrzeug.kennzeichen).all()

    # Patienten für Select (nur zugewiesene, wenn kein Admin)
    if current_user.is_admin:
        from app.models import Patient
        patienten = Patient.query.filter_by(
            company_id=cid, deleted_at=None, status='AKTIV'
        ).order_by(Patient.nachname).all()
    else:
        from app.models import Patient, EmployeePatientAssignment
        ids = db.session.query(EmployeePatientAssignment.patient_id).filter_by(
            employee_id=current_user.id, is_active=True
        ).all()
        patienten = Patient.query.filter(
            Patient.id.in_([i[0] for i in ids]),
            Patient.deleted_at == None
        ).order_by(Patient.nachname).all()

    preselect = fahrzeug_id
    errors = {}
    form_data = {'datum': date.today().strftime('%Y-%m-%d'),
                 'fahrzeug_id': fahrzeug_id or ''}

    if request.method == 'POST':
        form_data = request.form.to_dict()
        fzg_id   = form_data.get('fahrzeug_id', '').strip()
        km_start = _parse_int(form_data.get('km_start'))
        km_end   = _parse_int(form_data.get('km_end'))

        if not fzg_id:
            errors['fahrzeug_id'] = 'Bitte Fahrzeug wählen'
        if km_start is None:
            errors['km_start'] = 'Pflichtfeld'
        if km_end is None:
            errors['km_end'] = 'Pflichtfeld'
        elif km_start is not None and km_end <= km_start:
            errors['km_end'] = 'Endstand muss größer als Startstand sein'

        fzg = Fahrzeug.query.filter_by(
            id=fzg_id, company_id=cid, deleted_at=None
        ).first() if fzg_id else None
        if not fzg:
            errors['fahrzeug_id'] = 'Fahrzeug nicht gefunden'

        if not errors:
            eintrag = Kilometerbuch(
                company_id=cid,
                fahrzeug_id=fzg_id,
                employee_id=current_user.id,
                patient_id=form_data.get('patient_id') or None,
                datum=_parse_date(form_data.get('datum')) or date.today(),
                km_start=km_start,
                km_end=km_end,
                abfahrt_ort=form_data.get('abfahrt_ort', '').strip(),
                ziel_ort=form_data.get('ziel_ort', '').strip(),
                zweck=form_data.get('zweck', 'PATIENTENBESUCH'),
                kraftstoff_kosten=_parse_decimal(form_data.get('kraftstoff_kosten')),
                kraftstoff_liter=_parse_decimal(form_data.get('kraftstoff_liter')),
                bemerkungen=form_data.get('bemerkungen', '').strip(),
            )
            db.session.add(eintrag)
            # Kilometerstand des Fahrzeugs aktualisieren
            if not fzg.km_stand or km_end > fzg.km_stand:
                fzg.km_stand = km_end
                fzg.km_stand_datum = eintrag.datum
            db.session.commit()
            flash(f'✓ Fahrt ({eintrag.km_gesamt} km) eingetragen.', 'success')
            if current_user.is_admin:
                return redirect(url_for('fuhrpark.detail', fahrzeug_id=fzg_id))
            else:
                return redirect(url_for('fuhrpark.meine_fahrten'))

    return render_template('fuhrpark/km_form.html',
                           fahrzeuge=fahrzeuge,
                           patienten=patienten,
                           form_data=form_data,
                           errors=errors,
                           preselect=preselect)


# ─────────────────────────────────────────────────────────────
# MEINE FAHRTEN (FAHRER-Ansicht)
# ─────────────────────────────────────────────────────────────

@fuhrpark_bp.route('/meine-fahrten')
@login_required
def meine_fahrten():
    _can_access()
    monat = request.args.get('monat', date.today().strftime('%Y-%m'))
    try:
        year, month = int(monat[:4]), int(monat[5:7])
        von  = date(year, month, 1)
        bis  = date(year, month+1, 1) - timedelta(days=1) if month < 12 else date(year, 12, 31)
    except Exception:
        von = date.today().replace(day=1)
        bis = date.today()

    fahrten = Kilometerbuch.query.filter(
        Kilometerbuch.employee_id == current_user.id,
        Kilometerbuch.datum >= von,
        Kilometerbuch.datum <= bis,
    ).order_by(Kilometerbuch.datum.desc()).all()

    km_gesamt  = sum(f.km_gesamt for f in fahrten)
    tankkosten = sum(float(f.kraftstoff_kosten) for f in fahrten if f.kraftstoff_kosten)

    return render_template('fuhrpark/meine_fahrten.html',
                           fahrten=fahrten,
                           km_gesamt=km_gesamt,
                           tankkosten=tankkosten,
                           monat=monat, von=von, bis=bis)


# ─────────────────────────────────────────────────────────────
# SCHADENSMELDUNG
# ─────────────────────────────────────────────────────────────

@fuhrpark_bp.route('/<fahrzeug_id>/schaden/neu', methods=['GET', 'POST'])
@login_required
def schaden_neu(fahrzeug_id):
    _can_access()
    f = Fahrzeug.query.filter_by(
        id=fahrzeug_id, company_id=current_user.company_id, deleted_at=None
    ).first_or_404()

    if request.method == 'POST':
        beschreibung = request.form.get('beschreibung', '').strip()
        if not beschreibung:
            flash('Beschreibung ist erforderlich.', 'danger')
        else:
            s = Schadensmeldung(
                company_id=current_user.company_id,
                fahrzeug_id=f.id,
                employee_id=current_user.id,
                datum=_parse_date(request.form.get('datum')) or date.today(),
                beschreibung=beschreibung,
                ort=request.form.get('ort', '').strip(),
                versicherung_gemeldet='versicherung_gemeldet' in request.form,
                reparatur_kosten=_parse_decimal(request.form.get('reparatur_kosten')),
                status='OFFEN',
            )
            db.session.add(s)
            # Fahrzeug in Werkstatt setzen wenn angeklickt
            if 'in_werkstatt' in request.form:
                f.status = 'WERKSTATT'
            db.session.commit()
            flash(f'✓ Schadensmeldung für {f.kennzeichen} gespeichert.', 'success')
            return redirect(url_for('fuhrpark.detail', fahrzeug_id=f.id))

    return render_template('fuhrpark/schaden_form.html',
                           fahrzeug=f,
                           heute=date.today().strftime('%Y-%m-%d'))


@fuhrpark_bp.route('/schaden/<schaden_id>/status', methods=['POST'])
@login_required
@admin_required
def schaden_status(schaden_id):
    s = Schadensmeldung.query.filter_by(
        id=schaden_id, company_id=current_user.company_id
    ).first_or_404()
    neuer_status = request.form.get('status', 'OFFEN')
    s.status = neuer_status
    # Wenn erledigt → Fahrzeug wieder AKTIV
    if neuer_status == 'ERLEDIGT' and s.fahrzeug.status == 'WERKSTATT':
        s.fahrzeug.status = 'AKTIV'
    db.session.commit()
    flash(f'✓ Status aktualisiert: {neuer_status}', 'success')
    return redirect(url_for('fuhrpark.detail', fahrzeug_id=s.fahrzeug_id))


# ─────────────────────────────────────────────────────────────
# MONATSBERICHT
# ─────────────────────────────────────────────────────────────

@fuhrpark_bp.route('/bericht')
@login_required
@admin_required
def bericht():
    cid   = current_user.company_id
    monat = request.args.get('monat', date.today().strftime('%Y-%m'))
    try:
        year, month = int(monat[:4]), int(monat[5:7])
        von  = date(year, month, 1)
        bis  = (date(year, month+1, 1) - timedelta(days=1)) if month < 12 else date(year, 12, 31)
    except Exception:
        von = date.today().replace(day=1)
        bis = date.today()
        monat = date.today().strftime('%Y-%m')

    fahrten = Kilometerbuch.query.filter(
        Kilometerbuch.company_id == cid,
        Kilometerbuch.datum >= von,
        Kilometerbuch.datum <= bis,
    ).order_by(Kilometerbuch.datum).all()

    # Gruppierung nach Fahrzeug
    by_fzg = {}
    for eintrag in fahrten:
        fid = eintrag.fahrzeug_id
        if fid not in by_fzg:
            by_fzg[fid] = {'fahrzeug': eintrag.fahrzeug, 'fahrten': [], 'km': 0, 'kosten': Decimal('0')}
        by_fzg[fid]['fahrten'].append(eintrag)
        by_fzg[fid]['km'] += eintrag.km_gesamt
        if eintrag.kraftstoff_kosten:
            by_fzg[fid]['kosten'] += eintrag.kraftstoff_kosten

    gesamt_km     = sum(e.km_gesamt for e in fahrten)
    gesamt_kosten = sum(float(e.kraftstoff_kosten) for e in fahrten if e.kraftstoff_kosten)

    return render_template('fuhrpark/bericht.html',
                           by_fzg=by_fzg,
                           fahrten=fahrten,
                           gesamt_km=gesamt_km,
                           gesamt_kosten=gesamt_kosten,
                           monat=monat, von=von, bis=bis)
