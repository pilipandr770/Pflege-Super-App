"""
Privatrechnung — Abrechnung für Selbstzahler / Privatpatienten.

Pflegeleistungen nach § 4 Nr. 16 UStG sind i.d.R. steuerbefreit (0 % MwSt).
Rechnungs-Nr.: PRIV-YYYY-NNN
Status: ENTWURF → VERSENDET → BEZAHLT / MAHNUNG1 / MAHNUNG2 / ABGESCHRIEBEN
"""
import json
from datetime import date, timedelta
from decimal import Decimal
from flask import (Blueprint, render_template, redirect, url_for,
                   flash, request, send_file, current_app)
from flask_login import login_required, current_user
from app.extensions import db
from app.models import Privatrechnung, Patient, Company
from app.utils.auth import log_action

privatrechnung_bp = Blueprint('privatrechnung', __name__, url_prefix='/privatrechnung')

STATUS_LABELS = {
    'ENTWURF':      ('Entwurf',       'secondary'),
    'VERSENDET':    ('Versendet',     'primary'),
    'BEZAHLT':      ('Bezahlt',       'success'),
    'MAHNUNG1':     ('1. Mahnung',    'warning'),
    'MAHNUNG2':     ('2. Mahnung',    'danger'),
    'ABGESCHRIEBEN':('Abgeschrieben', 'dark'),
}

MWST_SAETZE = [
    (0,  '0 % (steuerbefreit §4 Nr.16 UStG)'),
    (7,  '7 %'),
    (19, '19 %'),
]


def _next_rechnung_nr(company_id):
    year = date.today().year
    last = (Privatrechnung.query
            .filter_by(company_id=company_id)
            .filter(Privatrechnung.rechnung_nr.like(f'PRIV-{year}-%'))
            .order_by(Privatrechnung.created_at.desc())
            .first())
    if last and last.rechnung_nr:
        try:
            n = int(last.rechnung_nr.split('-')[-1]) + 1
        except ValueError:
            n = 1
    else:
        n = 1
    return f'PRIV-{year}-{n:03d}'


def _get(rechnung_id):
    return Privatrechnung.query.filter_by(
        id=rechnung_id, company_id=current_user.company_id
    ).first_or_404()


def _calc_totals(positionen):
    netto = Decimal('0')
    mwst  = Decimal('0')
    for p in positionen:
        gesamt = Decimal(str(p.get('gesamtpreis', 0) or 0))
        netto += gesamt
        satz   = Decimal(str(p.get('mwst_satz', 0) or 0)) / 100
        mwst  += gesamt * satz
    brutto = netto + mwst
    return float(netto), float(mwst), float(brutto)


# ── Übersicht ─────────────────────────────────────────────────

@privatrechnung_bp.route('/')
@login_required
def index():
    status_filter  = request.args.get('status', '')
    patient_filter = request.args.get('patient_id', '')

    q = Privatrechnung.query.filter_by(company_id=current_user.company_id)
    if status_filter:
        q = q.filter_by(status=status_filter)
    if patient_filter:
        q = q.filter_by(patient_id=patient_filter)

    rechnungen = q.order_by(Privatrechnung.rechnungsdatum.desc()).all()
    patients   = (Patient.query
                  .filter_by(company_id=current_user.company_id, deleted_at=None)
                  .order_by(Patient.nachname).all())

    # Summen
    offen_summe  = sum(float(r.betrag_brutto or 0)
                       for r in rechnungen if r.status not in ('BEZAHLT', 'ABGESCHRIEBEN'))
    bezahlt_summe = sum(float(r.betrag_brutto or 0)
                        for r in rechnungen if r.status == 'BEZAHLT')
    today = date.today()
    return render_template('privatrechnung/index.html',
                           rechnungen=rechnungen, patients=patients,
                           status_labels=STATUS_LABELS,
                           status_filter=status_filter,
                           patient_filter=patient_filter,
                           offen_summe=offen_summe,
                           bezahlt_summe=bezahlt_summe,
                           today=today)


# ── Neue Rechnung ─────────────────────────────────────────────

@privatrechnung_bp.route('/neu', methods=['GET', 'POST'])
@privatrechnung_bp.route('/neu/<patient_id>', methods=['GET', 'POST'])
@login_required
def new(patient_id=None):
    patients = (Patient.query
                .filter_by(company_id=current_user.company_id, deleted_at=None)
                .order_by(Patient.nachname).all())
    preselected = None
    if patient_id:
        preselected = Patient.query.filter_by(
            id=patient_id, company_id=current_user.company_id
        ).first_or_404()

    if request.method == 'POST':
        fd  = request.form
        pid = fd.get('patient_id')
        if not pid:
            flash('Bitte einen Patienten auswählen.', 'danger')
            return render_template('privatrechnung/form.html',
                                   patients=patients, preselected=preselected,
                                   mwst_saetze=MWST_SAETZE, today=date.today())

        # Positionen aufbauen
        bezeichnungen  = fd.getlist('pos_bezeichnung')
        mengen         = fd.getlist('pos_menge')
        einheiten      = fd.getlist('pos_einheit')
        einzelpreise   = fd.getlist('pos_einzelpreis')
        mwst_liste     = fd.getlist('pos_mwst')
        positionen = []
        for bez, menge, einheit, ep, mwst in zip(
                bezeichnungen, mengen, einheiten, einzelpreise, mwst_liste):
            if not bez.strip():
                continue
            try:
                menge_f = float(menge.replace(',', '.') or 1)
                ep_f    = float(ep.replace(',', '.') or 0)
                mwst_i  = int(mwst or 0)
            except ValueError:
                menge_f, ep_f, mwst_i = 1, 0, 0
            positionen.append({
                'bezeichnung': bez.strip(),
                'menge':       menge_f,
                'einheit':     einheit.strip() or 'Einh.',
                'einzelpreis': ep_f,
                'gesamtpreis': round(menge_f * ep_f, 2),
                'mwst_satz':   mwst_i,
            })

        netto, mwst_b, brutto = _calc_totals(positionen)

        try:
            rechnungsdatum = date.fromisoformat(fd.get('rechnungsdatum', ''))
        except ValueError:
            rechnungsdatum = date.today()

        zahlungsziel_tage = int(fd.get('zahlungsziel_tage', 14) or 14)
        faellig_am        = rechnungsdatum + timedelta(days=zahlungsziel_tage)

        r = Privatrechnung(
            company_id=current_user.company_id,
            patient_id=pid,
            created_by=current_user.id,
            rechnung_nr=_next_rechnung_nr(current_user.company_id),
            rechnungsdatum=rechnungsdatum,
            leistungsmonat=fd.get('leistungsmonat', '').strip() or None,
            positionen=json.dumps(positionen, ensure_ascii=False),
            betrag_netto=netto,
            mwst_betrag=mwst_b,
            betrag_brutto=brutto,
            zahlungsziel_tage=zahlungsziel_tage,
            faellig_am=faellig_am,
            status='ENTWURF',
            notizen=fd.get('notizen', '').strip() or None,
        )
        db.session.add(r)
        db.session.commit()
        log_action('RECHNUNG_CREATED', 'privatrechnungen', r.id,
                   new_values={'nr': r.rechnung_nr, 'betrag': str(brutto)})
        flash(f'Rechnung {r.rechnung_nr} erstellt.', 'success')
        return redirect(url_for('privatrechnung.show', rechnung_id=r.id))

    return render_template('privatrechnung/form.html',
                           patients=patients, preselected=preselected,
                           mwst_saetze=MWST_SAETZE, today=date.today())


# ── Ansicht ───────────────────────────────────────────────────

@privatrechnung_bp.route('/<rechnung_id>')
@login_required
def show(rechnung_id):
    r     = _get(rechnung_id)
    today = date.today()
    return render_template('privatrechnung/show.html', r=r,
                           status_labels=STATUS_LABELS, today=today)


# ── Status ändern ─────────────────────────────────────────────

@privatrechnung_bp.route('/<rechnung_id>/status', methods=['POST'])
@login_required
def update_status(rechnung_id):
    r          = _get(rechnung_id)
    new_status = request.form.get('status')
    if new_status not in STATUS_LABELS:
        flash('Ungültiger Status.', 'danger')
        return redirect(url_for('privatrechnung.show', rechnung_id=rechnung_id))

    r.status = new_status
    if new_status == 'BEZAHLT':
        raw = request.form.get('bezahlt_am', '')
        try:
            r.bezahlt_am = date.fromisoformat(raw) if raw else date.today()
        except ValueError:
            r.bezahlt_am = date.today()
        r.zahlungsart = request.form.get('zahlungsart', 'UEBERWEISUNG')

    db.session.commit()
    log_action('RECHNUNG_STATUS', 'privatrechnungen', r.id,
               new_values={'status': new_status})
    label = STATUS_LABELS[new_status][0]
    flash(f'Status auf „{label}" gesetzt.', 'success')
    return redirect(url_for('privatrechnung.show', rechnung_id=rechnung_id))


# ── PDF ───────────────────────────────────────────────────────

@privatrechnung_bp.route('/<rechnung_id>/pdf')
@login_required
def pdf(rechnung_id):
    r       = _get(rechnung_id)
    company = Company.query.get(current_user.company_id)
    try:
        from app.utils.pdf import generate_privatrechnung_pdf
        buf      = generate_privatrechnung_pdf(r, company)
        filename = f'Rechnung_{r.rechnung_nr}_{r.patient.full_name.replace(" ", "_")}.pdf'
        return send_file(buf, mimetype='application/pdf',
                         as_attachment=False, download_name=filename)
    except Exception as e:
        current_app.logger.error(f'Privatrechnung PDF error: {e}')
        flash('PDF-Erstellung fehlgeschlagen.', 'danger')
        return redirect(url_for('privatrechnung.show', rechnung_id=rechnung_id))
