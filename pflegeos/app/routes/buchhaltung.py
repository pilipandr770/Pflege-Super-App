"""
Buchhaltung — Kassenbuch, GuV-Bericht, Leistungsabrechnung, DATEV-Export.
Nur für Admins und Verwaltung (OFFICE-Rolle).
"""
import csv
import io
import json
from flask import (Blueprint, render_template, request, redirect,
                   url_for, flash, abort, Response)
from flask_login import login_required, current_user
from app.extensions import db
from app.models import KassenbuchEintrag, Leistungsnachweis, Patient, Employee
from app.utils.auth import admin_required, log_action
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from collections import defaultdict

buchhaltung_bp = Blueprint('buchhaltung', __name__, url_prefix='/buchhaltung')


def _buch_access():
    """Admin oder Verwaltung."""
    if not current_user.is_authenticated:
        abort(403)
    if current_user.is_admin or current_user.role == 'VERWALTUNG':
        return True
    abort(403)


def _parse_date(val):
    if not val:
        return None
    try:
        return datetime.strptime(val, '%Y-%m-%d').date()
    except (ValueError, TypeError):
        return None


def _parse_decimal(val):
    try:
        v = val.replace(',', '.') if val else ''
        return Decimal(v) if v else None
    except (ValueError, InvalidOperation):
        return None


def _monat_range(monat_str):
    """Gibt (von, bis) für YYYY-MM zurück."""
    try:
        y, m = int(monat_str[:4]), int(monat_str[5:7])
        von = date(y, m, 1)
        bis = date(y, m + 1, 1) - timedelta(days=1) if m < 12 else date(y, 12, 31)
        return von, bis
    except Exception:
        heute = date.today()
        return heute.replace(day=1), heute


# ─────────────────────────────────────────────────────────────
# DASHBOARD
# ─────────────────────────────────────────────────────────────

@buchhaltung_bp.route('/')
@login_required
def dashboard():
    _buch_access()
    cid   = current_user.company_id
    heute = date.today()
    monat = heute.strftime('%Y-%m')
    von, bis = _monat_range(monat)

    # Aktueller Monat
    eintraege = KassenbuchEintrag.query.filter(
        KassenbuchEintrag.company_id == cid,
        KassenbuchEintrag.deleted_at == None,
        KassenbuchEintrag.datum >= von,
        KassenbuchEintrag.datum <= bis,
    ).order_by(KassenbuchEintrag.datum.desc()).all()

    einnahmen_mtl = sum(float(e.betrag) for e in eintraege if e.art == 'EINNAHME')
    ausgaben_mtl  = sum(float(e.betrag) for e in eintraege if e.art == 'AUSGABE')
    saldo_mtl     = einnahmen_mtl - ausgaben_mtl

    # Jahres-Saldo
    von_jahr = date(heute.year, 1, 1)
    jahrein = db.session.query(
        db.func.sum(KassenbuchEintrag.betrag)
    ).filter(
        KassenbuchEintrag.company_id == cid,
        KassenbuchEintrag.deleted_at == None,
        KassenbuchEintrag.art == 'EINNAHME',
        KassenbuchEintrag.datum >= von_jahr,
    ).scalar() or 0

    jahraus = db.session.query(
        db.func.sum(KassenbuchEintrag.betrag)
    ).filter(
        KassenbuchEintrag.company_id == cid,
        KassenbuchEintrag.deleted_at == None,
        KassenbuchEintrag.art == 'AUSGABE',
        KassenbuchEintrag.datum >= von_jahr,
    ).scalar() or 0

    # Nicht abgerechnete Leistungen — Anzahl & Wert
    offene_lnw = Leistungsnachweis.query.filter(
        Leistungsnachweis.company_id == cid,
        Leistungsnachweis.abgerechnet == False,
    ).all()
    offene_wert = sum(
        float(l.leistung.preis or 0) for l in offene_lnw if l.leistung and l.leistung.preis
    )

    # Letzte 10 Einträge (alle Monate)
    recent = KassenbuchEintrag.query.filter(
        KassenbuchEintrag.company_id == cid,
        KassenbuchEintrag.deleted_at == None,
    ).order_by(KassenbuchEintrag.datum.desc(), KassenbuchEintrag.created_at.desc()).limit(10).all()

    return render_template('buchhaltung/dashboard.html',
                           einnahmen_mtl=einnahmen_mtl,
                           ausgaben_mtl=ausgaben_mtl,
                           saldo_mtl=saldo_mtl,
                           jahrein=float(jahrein),
                           jahraus=float(jahraus),
                           saldo_jahr=float(jahrein) - float(jahraus),
                           offene_lnw=len(offene_lnw),
                           offene_wert=offene_wert,
                           recent=recent,
                           monat=monat,
                           monat_label=von.strftime('%B %Y'))


# ─────────────────────────────────────────────────────────────
# EINTRAG NEU / BEARBEITEN
# ─────────────────────────────────────────────────────────────

@buchhaltung_bp.route('/eintrag/neu', methods=['GET', 'POST'])
@login_required
def eintrag_neu():
    _buch_access()
    cid = current_user.company_id

    patienten = Patient.query.filter_by(
        company_id=cid, deleted_at=None, status='AKTIV'
    ).order_by(Patient.nachname).all()

    errors    = {}
    form_data = {
        'datum': date.today().strftime('%Y-%m-%d'),
        'art': request.args.get('art', 'EINNAHME'),
    }

    if request.method == 'POST':
        form_data = request.form.to_dict()
        art     = form_data.get('art', '').strip()
        kat     = form_data.get('kategorie', '').strip()
        betrag  = _parse_decimal(form_data.get('betrag', ''))
        datum   = _parse_date(form_data.get('datum'))

        if art not in ('EINNAHME', 'AUSGABE'):
            errors['art'] = 'Pflichtfeld'
        if not kat:
            errors['kategorie'] = 'Pflichtfeld'
        if betrag is None or betrag <= 0:
            errors['betrag'] = 'Betrag muss größer als 0 sein'
        if datum is None:
            errors['datum'] = 'Ungültiges Datum'

        if not errors:
            eintrag = KassenbuchEintrag(
                company_id=cid,
                employee_id=current_user.id,
                patient_id=form_data.get('patient_id') or None,
                datum=datum,
                art=art,
                kategorie=kat,
                betrag=betrag,
                beschreibung=form_data.get('beschreibung', '').strip(),
                beleg_nr=form_data.get('beleg_nr', '').strip(),
            )
            db.session.add(eintrag)
            db.session.commit()
            log_action('CREATE', 'KassenbuchEintrag', eintrag.id)
            flash(f'✓ Eintrag ({art.lower()}: {betrag} €) gespeichert.', 'success')
            return redirect(url_for('buchhaltung.kassenbuch'))

    return render_template('buchhaltung/eintrag_form.html',
                           form_data=form_data,
                           errors=errors,
                           patienten=patienten,
                           einnahmen_kat=KassenbuchEintrag.EINNAHMEN_KATEGORIEN,
                           ausgaben_kat=KassenbuchEintrag.AUSGABEN_KATEGORIEN)


@buchhaltung_bp.route('/eintrag/<eintrag_id>/loeschen', methods=['POST'])
@login_required
@admin_required
def eintrag_loeschen(eintrag_id):
    e = KassenbuchEintrag.query.filter_by(
        id=eintrag_id, company_id=current_user.company_id
    ).first_or_404()
    e.deleted_at = datetime.utcnow()
    db.session.commit()
    flash('Eintrag gelöscht.', 'info')
    return redirect(request.referrer or url_for('buchhaltung.kassenbuch'))


# ─────────────────────────────────────────────────────────────
# KASSENBUCH (Hauptbuch)
# ─────────────────────────────────────────────────────────────

@buchhaltung_bp.route('/kassenbuch')
@login_required
def kassenbuch():
    _buch_access()
    cid   = current_user.company_id
    monat = request.args.get('monat', date.today().strftime('%Y-%m'))
    art_filter = request.args.get('art', '')         # EINNAHME | AUSGABE | ''
    kat_filter = request.args.get('kategorie', '')

    von, bis = _monat_range(monat)

    q = KassenbuchEintrag.query.filter(
        KassenbuchEintrag.company_id == cid,
        KassenbuchEintrag.deleted_at == None,
        KassenbuchEintrag.datum >= von,
        KassenbuchEintrag.datum <= bis,
    )
    if art_filter:
        q = q.filter(KassenbuchEintrag.art == art_filter)
    if kat_filter:
        q = q.filter(KassenbuchEintrag.kategorie == kat_filter)

    eintraege = q.order_by(KassenbuchEintrag.datum.desc(),
                           KassenbuchEintrag.created_at.desc()).all()

    einnahmen = sum(float(e.betrag) for e in eintraege if e.art == 'EINNAHME')
    ausgaben  = sum(float(e.betrag) for e in eintraege if e.art == 'AUSGABE')

    return render_template('buchhaltung/kassenbuch.html',
                           eintraege=eintraege,
                           einnahmen=einnahmen,
                           ausgaben=ausgaben,
                           saldo=einnahmen - ausgaben,
                           monat=monat, von=von, bis=bis,
                           art_filter=art_filter,
                           kat_filter=kat_filter,
                           alle_kategorien={
                               **KassenbuchEintrag.EINNAHMEN_KATEGORIEN,
                               **KassenbuchEintrag.AUSGABEN_KATEGORIEN,
                           })


# ─────────────────────────────────────────────────────────────
# GuV-BERICHT (Gewinn & Verlust)
# ─────────────────────────────────────────────────────────────

@buchhaltung_bp.route('/bericht')
@login_required
def bericht():
    _buch_access()
    cid  = current_user.company_id
    jahr = int(request.args.get('jahr', date.today().year))

    von_jahr = date(jahr, 1, 1)
    bis_jahr = date(jahr, 12, 31)

    eintraege = KassenbuchEintrag.query.filter(
        KassenbuchEintrag.company_id == cid,
        KassenbuchEintrag.deleted_at == None,
        KassenbuchEintrag.datum >= von_jahr,
        KassenbuchEintrag.datum <= bis_jahr,
    ).all()

    # ── Monatliche Aggregation (für Chart) ──
    monate_labels = [f"{m:02d}/{str(jahr)[2:]}" for m in range(1, 13)]
    ein_by_m  = defaultdict(float)
    aus_by_m  = defaultdict(float)
    for e in eintraege:
        m = e.datum.month
        if e.art == 'EINNAHME':
            ein_by_m[m] += float(e.betrag)
        else:
            aus_by_m[m] += float(e.betrag)

    ein_data = [round(ein_by_m[m], 2) for m in range(1, 13)]
    aus_data = [round(aus_by_m[m], 2) for m in range(1, 13)]

    # ── Kategorie-Aufschlüsselung ──
    kat_ein = defaultdict(float)
    kat_aus = defaultdict(float)
    for e in eintraege:
        label = e.kategorie_label
        if e.art == 'EINNAHME':
            kat_ein[label] += float(e.betrag)
        else:
            kat_aus[label] += float(e.betrag)

    # ── Monatliche Zusammenfassung für Tabelle ──
    monthly = []
    for m in range(1, 13):
        von_m = date(jahr, m, 1)
        bis_m = date(jahr, m + 1, 1) - timedelta(days=1) if m < 12 else date(jahr, 12, 31)
        ein = ein_by_m[m]
        aus = aus_by_m[m]
        monthly.append({
            'monat': von_m.strftime('%B'),
            'monat_str': f"{jahr}-{m:02d}",
            'einnahmen': ein,
            'ausgaben': aus,
            'saldo': ein - aus,
        })

    gesamt_ein = sum(float(e.betrag) for e in eintraege if e.art == 'EINNAHME')
    gesamt_aus = sum(float(e.betrag) for e in eintraege if e.art == 'AUSGABE')

    # Verfügbare Jahre (für Select)
    jahre_raw = db.session.query(
        db.func.extract('year', KassenbuchEintrag.datum)
    ).filter(
        KassenbuchEintrag.company_id == cid,
        KassenbuchEintrag.deleted_at == None,
    ).distinct().all()
    jahre = sorted({int(y[0]) for y in jahre_raw if y[0]}, reverse=True)
    if not jahre:
        jahre = [date.today().year]

    return render_template('buchhaltung/bericht.html',
                           jahr=jahr, jahre=jahre,
                           monate_labels=monate_labels,
                           ein_data=ein_data,
                           aus_data=aus_data,
                           kat_ein=dict(sorted(kat_ein.items(), key=lambda x: -x[1])),
                           kat_aus=dict(sorted(kat_aus.items(), key=lambda x: -x[1])),
                           monthly=monthly,
                           gesamt_ein=gesamt_ein,
                           gesamt_aus=gesamt_aus,
                           saldo=gesamt_ein - gesamt_aus)


# ─────────────────────────────────────────────────────────────
# LEISTUNGS-AUSWERTUNG (Abrechnung aus Leistungsnachweisen)
# ─────────────────────────────────────────────────────────────

@buchhaltung_bp.route('/leistungen')
@login_required
def leistungen():
    _buch_access()
    cid   = current_user.company_id
    monat = request.args.get('monat', date.today().strftime('%Y-%m'))
    von, bis = _monat_range(monat)

    lnw = Leistungsnachweis.query.filter(
        Leistungsnachweis.company_id == cid,
        Leistungsnachweis.durchgefuehrt_am >= von,
        Leistungsnachweis.durchgefuehrt_am <= bis,
    ).order_by(Leistungsnachweis.durchgefuehrt_am).all()

    # Gruppieren nach Patient
    by_patient = defaultdict(lambda: {
        'patient': None, 'eintraege': [], 'anzahl': 0,
        'minuten': 0, 'wert': 0.0, 'abgerechnet': 0,
    })
    for l in lnw:
        pid = l.patient_id
        by_patient[pid]['patient']    = l.patient
        by_patient[pid]['eintraege'].append(l)
        by_patient[pid]['anzahl']     += 1
        by_patient[pid]['minuten']    += l.dauer_minuten or 0
        by_patient[pid]['wert']       += float(l.leistung.preis or 0) if l.leistung else 0
        if l.abgerechnet:
            by_patient[pid]['abgerechnet'] += 1

    # Gesamt-Stats
    gesamt_wert        = sum(d['wert'] for d in by_patient.values())
    gesamt_abgerechnet = sum(d['abgerechnet'] for d in by_patient.values())
    gesamt_offen       = sum(
        d['anzahl'] - d['abgerechnet'] for d in by_patient.values()
    )

    return render_template('buchhaltung/leistungen.html',
                           by_patient=by_patient,
                           gesamt_wert=gesamt_wert,
                           gesamt_abgerechnet=gesamt_abgerechnet,
                           gesamt_offen=gesamt_offen,
                           monat=monat, von=von, bis=bis,
                           gesamt_lnw=len(lnw))


@buchhaltung_bp.route('/leistungen/als-einnahme', methods=['POST'])
@login_required
@admin_required
def leistungen_buchen():
    """Markiert Leistungsnachweise als abgerechnet und erstellt Kassenbucheintrag."""
    cid = current_user.company_id
    ids_raw = request.form.get('lnw_ids', '[]')
    try:
        lnw_ids = json.loads(ids_raw)
    except Exception:
        lnw_ids = []

    if not lnw_ids:
        flash('Keine Leistungsnachweise ausgewählt.', 'warning')
        return redirect(url_for('buchhaltung.leistungen'))

    lnw_liste = Leistungsnachweis.query.filter(
        Leistungsnachweis.id.in_(lnw_ids),
        Leistungsnachweis.company_id == cid,
        Leistungsnachweis.abgerechnet == False,
    ).all()

    if not lnw_liste:
        flash('Keine offenen Leistungsnachweise gefunden.', 'warning')
        return redirect(url_for('buchhaltung.leistungen'))

    # Gesamtwert berechnen
    wert = sum(float(l.leistung.preis or 0) for l in lnw_liste if l.leistung)
    patient = lnw_liste[0].patient

    # Als abgerechnet markieren
    for l in lnw_liste:
        l.abgerechnet = True

    # Kassenbucheintrag anlegen
    beschreibung = (
        f"Pflegekasse {patient.krankenversicherung or 'unbekannt'} — "
        f"{patient.full_name} — {len(lnw_liste)} Leistungen "
        f"({lnw_liste[0].durchgefuehrt_am.strftime('%m/%Y')})"
    )
    eintrag = KassenbuchEintrag(
        company_id=cid,
        employee_id=current_user.id,
        patient_id=patient.id,
        datum=date.today(),
        art='EINNAHME',
        kategorie='PFLEGEKASSE',
        betrag=Decimal(str(round(wert, 2))),
        beschreibung=beschreibung,
        leistungs_ids=json.dumps(lnw_ids),
    )
    db.session.add(eintrag)
    db.session.commit()

    flash(f'✓ {len(lnw_liste)} Leistungen als abgerechnet markiert — '
          f'Einnahme {wert:.2f} € ins Kassenbuch gebucht.', 'success')
    return redirect(url_for('buchhaltung.kassenbuch'))


# ─────────────────────────────────────────────────────────────
# DATEV-EXPORT (CSV für Steuerberater)
# ─────────────────────────────────────────────────────────────

@buchhaltung_bp.route('/export.csv')
@login_required
@admin_required
def export_datev():
    """
    Exportiert alle Kassenbucheinträge als DATEV-ähnliches CSV.
    Filter: ?monat=2026-05 oder ?von=2026-01-01&bis=2026-12-31
    """
    cid = current_user.company_id

    monat = request.args.get('monat')
    von_str = request.args.get('von')
    bis_str = request.args.get('bis')

    if monat:
        von, bis = _monat_range(monat)
    elif von_str and bis_str:
        von = _parse_date(von_str) or date.today().replace(day=1)
        bis = _parse_date(bis_str) or date.today()
    else:
        # Standard: laufendes Jahr
        von = date(date.today().year, 1, 1)
        bis = date.today()

    eintraege = KassenbuchEintrag.query.filter(
        KassenbuchEintrag.company_id == cid,
        KassenbuchEintrag.deleted_at == None,
        KassenbuchEintrag.datum >= von,
        KassenbuchEintrag.datum <= bis,
    ).order_by(KassenbuchEintrag.datum.asc()).all()

    si = io.StringIO()
    cw = csv.writer(si, delimiter=';')

    # DATEV-Kopfzeile
    cw.writerow([
        'Belegdatum', 'Belegnummer', 'Buchungstext',
        'Umsatz (soll)', 'Soll/Haben',
        'Konto', 'Gegenkonto', 'Kategorie',
        'Patient', 'Erstellt von',
    ])

    # DATEV-Konten-Mapping (vereinfacht, SKR03-orientiert)
    konto_map = {
        'PFLEGEKASSE':     ('8400', '1200'),
        'PRIVATPATIENT':   ('8400', '1200'),
        'EIGENANTEIL':     ('8400', '1200'),
        'FOERDERUNG':      ('8900', '1200'),
        'SONSTIGE_EINNAHME': ('8900', '1200'),
        'KRAFTSTOFF':      ('1200', '4530'),
        'FAHRZEUG_WARTUNG':('1200', '4540'),
        'GEHAELTER':       ('1200', '4100'),
        'MIETE':           ('1200', '4210'),
        'MATERIAL_PFLEGE': ('1200', '3400'),
        'BUERO':           ('1200', '4930'),
        'VERSICHERUNG':    ('1200', '4360'),
        'STEUER':          ('1200', '4900'),
        'FORTBILDUNG':     ('1200', '4940'),
        'SONSTIGE_AUSGABE':('1200', '4999'),
    }

    for e in eintraege:
        soll_haben = 'S' if e.art == 'EINNAHME' else 'H'
        konto, gkonto = konto_map.get(e.kategorie, ('1200', '9999'))
        patient_name = e.patient.full_name if e.patient else ''
        ersteller    = e.ersteller.full_name if e.ersteller else ''
        cw.writerow([
            e.datum.strftime('%d.%m.%Y'),
            e.beleg_nr or '',
            e.beschreibung or '',
            str(e.betrag).replace('.', ','),
            soll_haben,
            konto,
            gkonto,
            e.kategorie_label,
            patient_name,
            ersteller,
        ])

    filename = f"Kassenbuch_{von.strftime('%Y%m%d')}_{bis.strftime('%Y%m%d')}.csv"
    return Response(
        '﻿' + si.getvalue(),
        mimetype='text/csv; charset=utf-8',
        headers={'Content-Disposition': f'attachment; filename="{filename}"'}
    )
