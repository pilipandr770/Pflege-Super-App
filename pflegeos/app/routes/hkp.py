"""
Häusliche Krankenpflege — Verordnungen (§37 SGB V, Muster 12).

Ermöglicht die Erfassung ärztlicher HKP-Verordnungen, Statusverfolgung
(ENTWURF → EINGEREICHT → GENEHMIGT/ABGELEHNT) und PDF-Druck.
"""
import json
from datetime import date, datetime
from flask import (Blueprint, render_template, redirect, url_for,
                   flash, request, send_file, current_app)
from flask_login import login_required, current_user
from app.extensions import db
from app.models import HkpVerordnung, Patient, Company
from app.utils.auth import admin_required, log_action

hkp_bp = Blueprint('hkp', __name__, url_prefix='/hkp')

STATUS_LABELS = {
    'ENTWURF':     ('Entwurf',     'secondary'),
    'EINGEREICHT': ('Eingereicht', 'primary'),
    'GENEHMIGT':   ('Genehmigt',   'success'),
    'ABGELEHNT':   ('Abgelehnt',   'danger'),
}

# Standard-Behandlungspflege-Leistungen §37 SGB V
BP_LEISTUNGEN = [
    'Wundversorgung / Verbandwechsel',
    'Medikamentengabe (oral)',
    'Injektion (subcutan / intramuskulär)',
    'Insulingabe',
    'Blutdruckmessung / Vitalzeichenkontrolle',
    'Blutzuckermessung',
    'Katheterpflege / Katheterisierung',
    'Stomapflege',
    'Infusionstherapie',
    'Kompressionstherapie',
    'Inhalationstherapie',
    'Krankenbeobachtung',
    'Dekubitusprophylaxe / -behandlung',
    'Mobilisation nach Arztanordnung',
    'Peg-Sonden-Versorgung',
    'Portversorgung',
    'Einläufe / Klistiere',
    'Absaugen der Atemwege',
    'Sonstige Behandlungspflege',
]


# ── Übersicht ─────────────────────────────────────────────────────────────────

@hkp_bp.route('/')
@login_required
def index():
    status_filter = request.args.get('status', '')
    patient_filter = request.args.get('patient_id', '')

    q = HkpVerordnung.query.filter_by(company_id=current_user.company_id)
    if status_filter:
        q = q.filter_by(status=status_filter)
    if patient_filter:
        q = q.filter_by(patient_id=patient_filter)

    verordnungen = q.order_by(HkpVerordnung.gueltig_von.desc()).all()

    patients = Patient.query.filter_by(
        company_id=current_user.company_id, deleted_at=None
    ).order_by(Patient.nachname).all()

    today = date.today()
    return render_template('hkp/index.html',
                           verordnungen=verordnungen,
                           patients=patients,
                           status_labels=STATUS_LABELS,
                           status_filter=status_filter,
                           patient_filter=patient_filter,
                           today=today)


# ── Neue Verordnung ───────────────────────────────────────────────────────────

@hkp_bp.route('/neu', methods=['GET', 'POST'])
@hkp_bp.route('/neu/<patient_id>', methods=['GET', 'POST'])
@login_required
def new(patient_id=None):
    patients = Patient.query.filter_by(
        company_id=current_user.company_id, deleted_at=None
    ).order_by(Patient.nachname).all()

    preselected = None
    if patient_id:
        preselected = Patient.query.filter_by(
            id=patient_id, company_id=current_user.company_id
        ).first_or_404()

    if request.method == 'POST':
        fd = request.form
        pid = fd.get('patient_id')
        if not pid:
            flash('Bitte einen Patienten auswählen.', 'danger')
            return render_template('hkp/form.html', verordnung=None,
                                   patients=patients, preselected=preselected,
                                   bp_leistungen=BP_LEISTUNGEN)

        # Diagnosen aus Formular aufbauen
        diagnosen = []
        for i in range(1, 6):
            icd = fd.get(f'icd_{i}', '').strip()
            txt = fd.get(f'diag_{i}', '').strip()
            if icd or txt:
                diagnosen.append({'icd': icd, 'text': txt})

        # Leistungen aus Formular aufbauen
        leistungen = []
        typen    = fd.getlist('l_typ')
        bezeichn = fd.getlist('l_bezeichnung')
        haeufgk  = fd.getlist('l_haeufigkeit')
        for typ, bez, hae in zip(typen, bezeichn, haeufgk):
            if bez.strip():
                leistungen.append({
                    'typ': typ,
                    'bezeichnung': bez.strip(),
                    'haeufigkeit': hae.strip(),
                })

        try:
            gueltig_von = date.fromisoformat(fd.get('gueltig_von', ''))
            gueltig_bis = date.fromisoformat(fd.get('gueltig_bis', ''))
        except ValueError:
            flash('Ungültiger Zeitraum.', 'danger')
            return render_template('hkp/form.html', verordnung=None,
                                   patients=patients, preselected=preselected,
                                   bp_leistungen=BP_LEISTUNGEN)

        dauer = (gueltig_bis - gueltig_von).days // 7 + 1

        v = HkpVerordnung(
            company_id=current_user.company_id,
            patient_id=pid,
            created_by=current_user.id,
            arzt_name=fd.get('arzt_name', '').strip(),
            arzt_lanr=fd.get('arzt_lanr', '').strip() or None,
            arzt_bsnr=fd.get('arzt_bsnr', '').strip() or None,
            arzt_adresse=fd.get('arzt_adresse', '').strip() or None,
            arzt_telefon=fd.get('arzt_telefon', '').strip() or None,
            diagnosen=json.dumps(diagnosen, ensure_ascii=False),
            leistungen=json.dumps(leistungen, ensure_ascii=False),
            gueltig_von=gueltig_von,
            gueltig_bis=gueltig_bis,
            dauer_wochen=dauer,
            begruendung_langzeit=fd.get('begruendung_langzeit', '').strip() or None,
            notizen=fd.get('notizen', '').strip() or None,
            status='ENTWURF',
        )
        db.session.add(v)
        db.session.commit()
        log_action('HKP_CREATED', 'hkp_verordnungen', v.id,
                   new_values={'patient_id': pid, 'arzt': v.arzt_name})
        flash('Verordnung angelegt.', 'success')
        return redirect(url_for('hkp.show', verordnung_id=v.id))

    return render_template('hkp/form.html', verordnung=None,
                           patients=patients, preselected=preselected,
                           bp_leistungen=BP_LEISTUNGEN)


# ── Ansicht ───────────────────────────────────────────────────────────────────

@hkp_bp.route('/<verordnung_id>')
@login_required
def show(verordnung_id):
    v = _get(verordnung_id)
    today = date.today()
    return render_template('hkp/show.html', v=v,
                           status_labels=STATUS_LABELS, today=today)


# ── Status ändern ─────────────────────────────────────────────────────────────

@hkp_bp.route('/<verordnung_id>/status', methods=['POST'])
@login_required
def update_status(verordnung_id):
    v = _get(verordnung_id)
    new_status = request.form.get('status')
    if new_status not in STATUS_LABELS:
        flash('Ungültiger Status.', 'danger')
        return redirect(url_for('hkp.show', verordnung_id=verordnung_id))

    fd = request.form
    if new_status == 'EINGEREICHT' and not v.eingereicht_am:
        v.eingereicht_am = datetime.utcnow()
    elif new_status == 'GENEHMIGT':
        v.genehmigt_am       = datetime.utcnow()
        v.genehmigungsnummer = fd.get('genehmigungsnummer', '').strip() or None
    elif new_status == 'ABGELEHNT':
        v.ablehnungsgrund = fd.get('ablehnungsgrund', '').strip() or None

    v.status = new_status
    db.session.commit()
    log_action('HKP_STATUS', 'hkp_verordnungen', v.id,
               new_values={'status': new_status})
    label = STATUS_LABELS[new_status][0]
    flash(f'Status auf „{label}" gesetzt.', 'success')
    return redirect(url_for('hkp.show', verordnung_id=verordnung_id))


# ── PDF ───────────────────────────────────────────────────────────────────────

@hkp_bp.route('/<verordnung_id>/pdf')
@login_required
def pdf(verordnung_id):
    v       = _get(verordnung_id)
    company = Company.query.get(current_user.company_id)
    try:
        from app.utils.pdf import generate_hkp_pdf
        buf = generate_hkp_pdf(v, company)
        patient_name = v.patient.full_name.replace(' ', '_')
        filename = f"HKP_{patient_name}_{v.gueltig_von.strftime('%Y%m')}.pdf"
        return send_file(buf, mimetype='application/pdf',
                         as_attachment=False,
                         download_name=filename)
    except Exception as e:
        current_app.logger.error(f'HKP PDF error: {e}')
        flash('PDF-Erstellung fehlgeschlagen. ReportLab prüfen.', 'danger')
        return redirect(url_for('hkp.show', verordnung_id=verordnung_id))


# ── Helper ────────────────────────────────────────────────────────────────────

def _get(verordnung_id):
    return HkpVerordnung.query.filter_by(
        id=verordnung_id, company_id=current_user.company_id
    ).first_or_404()
