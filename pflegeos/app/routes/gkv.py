"""
GKV-Abrechnung nach SGB XI §105.

Erstellt monatliche Abrechnungspositionen je Patient,
berechnet Leistungsbeträge aus vorhandenen Leistungsnachweisen
und exportiert druckfertige PDF- und maschinenlesbare CSV-Dateien.
"""
import csv
import io
from datetime import date, datetime
from decimal import Decimal

from flask import (Blueprint, render_template, redirect, url_for, flash,
                   request, jsonify, make_response)
from flask_login import login_required, current_user

from app.extensions import db
from app.models import GkvAbrechnung, Patient, Leistungsnachweis, Company
from app.utils.auth import admin_required, log_action

gkv_bp = Blueprint('gkv', __name__, url_prefix='/gkv')

# ── Hilfskonstanten ───────────────────────────────────────────────────────────

STATUS_LABELS = {
    'ENTWURF':       ('Entwurf',       'secondary'),
    'EINGEREICHT':   ('Eingereicht',   'primary'),
    'GENEHMIGT':     ('Genehmigt',     'success'),
    'ABGELEHNT':     ('Abgelehnt',     'danger'),
    'TEILGENEHMIGT': ('Teilgenehmigt', 'warning'),
}

# SGB XI Sachleistungsbeträge je Pflegegrad (2024, vereinfacht)
SACHLEISTUNGEN_MAX = {
    '1': Decimal('0'),
    '2': Decimal('761'),
    '3': Decimal('1432'),
    '4': Decimal('1778'),
    '5': Decimal('2200'),
}


# ── Übersicht ─────────────────────────────────────────────────────────────────

@gkv_bp.route('/')
@login_required
@admin_required
def index():
    monat = request.args.get('monat', date.today().strftime('%Y-%m'))

    abrechnungen = GkvAbrechnung.query.filter_by(
        company_id=current_user.company_id,
        abrechnungsmonat=monat,
    ).order_by(GkvAbrechnung.status).all()

    # Alle verfügbaren Monate
    monate = db.session.query(GkvAbrechnung.abrechnungsmonat).filter_by(
        company_id=current_user.company_id
    ).distinct().order_by(GkvAbrechnung.abrechnungsmonat.desc()).all()
    monate = [m[0] for m in monate]
    if monat not in monate:
        monate = [monat] + monate

    gesamtbetrag = sum(a.gesamtbetrag or 0 for a in abrechnungen)

    return render_template('gkv/index.html',
                           abrechnungen=abrechnungen,
                           monat=monat,
                           monate=monate,
                           gesamtbetrag=gesamtbetrag,
                           status_labels=STATUS_LABELS)


# ── Abrechnung generieren ─────────────────────────────────────────────────────

@gkv_bp.route('/generieren', methods=['GET', 'POST'])
@login_required
@admin_required
def generieren():
    company = Company.query.get(current_user.company_id)

    if request.method == 'POST':
        monat = request.form.get('monat', '').strip()
        if not monat or len(monat) != 7:
            flash('Ungültiges Abrechnungsmonat.', 'danger')
            return redirect(url_for('gkv.generieren'))

        patienten = Patient.query.filter_by(
            company_id=current_user.company_id,
            status='AKTIV',
            deleted_at=None,
        ).all()

        year, month = int(monat[:4]), int(monat[5:])
        from calendar import monthrange
        _, last_day = monthrange(year, month)
        von = date(year, month, 1)
        bis = date(year, month, last_day)

        erstellt = 0
        uebersprungen = 0

        for patient in patienten:
            existing = GkvAbrechnung.query.filter_by(
                company_id=current_user.company_id,
                patient_id=patient.id,
                abrechnungsmonat=monat,
            ).first()
            if existing:
                uebersprungen += 1
                continue

            lns = Leistungsnachweis.query.filter(
                Leistungsnachweis.patient_id == patient.id,
                Leistungsnachweis.durchgefuehrt_am >= von,
                Leistungsnachweis.durchgefuehrt_am <= bis,
            ).all()

            if not lns:
                continue

            anzahl_einsaetze = len(lns)
            sachbetrag = sum(
                Decimal(str(ln.leistung.preis or 0)) for ln in lns if ln.leistung
            )
            # Kappen am SGB XI Maximum
            max_betrag = SACHLEISTUNGEN_MAX.get(patient.pflegegrad or '0', Decimal('0'))
            sachbetrag = min(sachbetrag, max_betrag) if max_betrag > 0 else sachbetrag

            abrechnung = GkvAbrechnung(
                company_id=current_user.company_id,
                patient_id=patient.id,
                created_by=current_user.id,
                abrechnungsmonat=monat,
                krankenkasse=patient.krankenversicherung,
                ik_nummer_dienst=company.ik_nummer,
                pflegegrad=patient.pflegegrad,
                sachleistungen_betrag=sachbetrag,
                gesamtbetrag=sachbetrag,
                anzahl_einsaetze=anzahl_einsaetze,
                status='ENTWURF',
            )
            db.session.add(abrechnung)
            erstellt += 1

        db.session.commit()
        log_action('GKV_GENERIERT', 'gkv_abrechnungen',
                   new_values={'monat': monat, 'erstellt': erstellt})
        flash(f'{erstellt} Abrechnungen generiert, {uebersprungen} bereits vorhanden.', 'success')
        return redirect(url_for('gkv.index', monat=monat))

    return render_template('gkv/generieren.html', company=company,
                           today_monat=date.today().strftime('%Y-%m'))


# ── Einzelne Abrechnung anzeigen / bearbeiten ─────────────────────────────────

@gkv_bp.route('/<abr_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def show(abr_id):
    abr = _get_abr(abr_id)

    if request.method == 'POST':
        fd = request.form
        abr.sachleistungen_betrag = _decimal(fd.get('sachleistungen_betrag'))
        abr.verhinderungspflege   = _decimal(fd.get('verhinderungspflege'))
        abr.pflegehilfsmittel     = _decimal(fd.get('pflegehilfsmittel'))
        abr.entlastungsbetrag     = _decimal(fd.get('entlastungsbetrag'))
        abr.ik_nummer_kasse       = fd.get('ik_nummer_kasse', '').strip() or None
        abr.notizen               = fd.get('notizen', '').strip() or None
        abr.gesamtbetrag          = (
            (abr.sachleistungen_betrag or 0) +
            (abr.verhinderungspflege or 0) +
            (abr.pflegehilfsmittel or 0) +
            (abr.entlastungsbetrag or 0)
        )
        db.session.commit()
        flash('Abrechnung aktualisiert.', 'success')
        return redirect(url_for('gkv.show', abr_id=abr_id))

    # Leistungsnachweise des Monats laden
    year, month = int(abr.abrechnungsmonat[:4]), int(abr.abrechnungsmonat[5:])
    from calendar import monthrange
    _, last_day = monthrange(year, month)
    lns = Leistungsnachweis.query.filter(
        Leistungsnachweis.patient_id == abr.patient_id,
        Leistungsnachweis.durchgefuehrt_am >= date(year, month, 1),
        Leistungsnachweis.durchgefuehrt_am <= date(year, month, last_day),
    ).order_by(Leistungsnachweis.durchgefuehrt_am).all()

    return render_template('gkv/show.html', abr=abr,
                           lns=lns, status_labels=STATUS_LABELS)


# ── Status ändern ─────────────────────────────────────────────────────────────

@gkv_bp.route('/<abr_id>/status', methods=['POST'])
@login_required
@admin_required
def update_status(abr_id):
    abr = _get_abr(abr_id)
    new_status = request.form.get('status')
    if new_status not in STATUS_LABELS:
        flash('Ungültiger Status.', 'danger')
        return redirect(url_for('gkv.show', abr_id=abr_id))

    if new_status == 'EINGEREICHT' and not abr.eingereicht_am:
        abr.eingereicht_am = datetime.utcnow()

    abr.status = new_status
    db.session.commit()
    log_action('GKV_STATUS', 'gkv_abrechnungen', abr_id,
               new_values={'status': new_status})
    flash(f'Status auf „{STATUS_LABELS[new_status][0]}" gesetzt.', 'success')
    return redirect(url_for('gkv.show', abr_id=abr_id))


# ── CSV-Export (maschinenlesbar für Übergabe an GKV-Software) ─────────────────

@gkv_bp.route('/export/csv')
@login_required
@admin_required
def export_csv():
    monat = request.args.get('monat', date.today().strftime('%Y-%m'))
    status_filter = request.args.get('status', '')

    q = GkvAbrechnung.query.filter_by(
        company_id=current_user.company_id,
        abrechnungsmonat=monat,
    )
    if status_filter:
        q = q.filter_by(status=status_filter)

    abrechnungen = q.order_by(GkvAbrechnung.patient_id).all()

    si = io.StringIO()
    si.write('﻿')  # UTF-8 BOM für Excel
    writer = csv.writer(si, delimiter=';')
    writer.writerow([
        'Abrechnungsmonat', 'Patient', 'Pflegegrad',
        'Krankenkasse', 'IK Kasse', 'IK Dienst',
        'Sachleistungen €', 'Verhinderungspflege €',
        'Pflegehilfsmittel €', 'Entlastungsbetrag €',
        'Gesamtbetrag €', 'Einsätze', 'Status',
    ])
    for a in abrechnungen:
        writer.writerow([
            a.abrechnungsmonat,
            a.patient.full_name,
            a.pflegegrad or '',
            a.krankenkasse or '',
            a.ik_nummer_kasse or '',
            a.ik_nummer_dienst or '',
            str(a.sachleistungen_betrag or 0).replace('.', ','),
            str(a.verhinderungspflege or 0).replace('.', ','),
            str(a.pflegehilfsmittel or 0).replace('.', ','),
            str(a.entlastungsbetrag or 0).replace('.', ','),
            str(a.gesamtbetrag or 0).replace('.', ','),
            a.anzahl_einsaetze or 0,
            STATUS_LABELS.get(a.status, (a.status,))[0],
        ])

    output = make_response(si.getvalue())
    filename = f'GKV_Abrechnung_{monat}.csv'
    output.headers['Content-Type'] = 'text/csv; charset=utf-8'
    output.headers['Content-Disposition'] = f'attachment; filename="{filename}"'
    log_action('GKV_EXPORT_CSV', 'gkv_abrechnungen', new_values={'monat': monat})
    return output


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_abr(abr_id):
    return GkvAbrechnung.query.filter_by(
        id=abr_id,
        company_id=current_user.company_id,
    ).first_or_404()


def _decimal(val):
    try:
        return Decimal(str(val).replace(',', '.')) if val else Decimal('0')
    except Exception:
        return Decimal('0')
