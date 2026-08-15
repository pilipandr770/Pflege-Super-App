"""
Pflegevertrag-Generator (§ 120 SGB XI).

Erstellt, verwaltet und druckt Pflegeverträge zwischen Pflegedienst und Patient.
Status-Workflow: ENTWURF → AKTIV (nach Unterschrift) → GEKUENDIGT / ABGELAUFEN
"""
import json
from datetime import date, datetime
from flask import (Blueprint, render_template, redirect, url_for,
                   flash, request, send_file, current_app)
from flask_login import login_required, current_user
from app.extensions import db
from app.models import Pflegevertrag, Patient, Company
from app.utils.auth import admin_required, log_action

pflegevertrag_bp = Blueprint('pflegevertrag', __name__, url_prefix='/pflegevertrag')

STATUS_LABELS = {
    'ENTWURF':    ('Entwurf',    'secondary'),
    'AKTIV':      ('Aktiv',      'success'),
    'GEKUENDIGT': ('Gekündigt',  'danger'),
    'ABGELAUFEN': ('Abgelaufen', 'warning'),
}

LEISTUNGSBEREICHE = [
    'Körperpflege (Waschen, Duschen, Baden)',
    'An- und Auskleiden',
    'Mundpflege und Zahnpflege',
    'Haarpflege und Rasur',
    'Ernährung (Vorbereitung / Eingabe)',
    'Mobilisation und Lagerung',
    'Ausscheidungshilfe / Inkontinenzversorgung',
    'Kompressionsstrümpfe an- und ausziehen',
    'Medikamentengabe (nach ärztl. Verordnung)',
    'Wundversorgung / Verbandwechsel',
    'Blutdruck- und Vitalzeichenkontrolle',
    'Insulingabe und Blutzuckermessung',
    'Injektion (subcutan / intramuskulär)',
    'Haushaltsführung (Einkauf, Reinigung, Wäsche)',
    'Begleitung zu Arztterminen',
    'Nacht- und Bereitschaftsdienst',
    'Sonstige Leistung',
]


def _next_vertrag_nr(company_id):
    """Generiert laufende Vertragsnummer PV-YYYY-NNN."""
    year = date.today().year
    last = (Pflegevertrag.query
            .filter_by(company_id=company_id)
            .filter(Pflegevertrag.vertrag_nr.like(f'PV-{year}-%'))
            .order_by(Pflegevertrag.created_at.desc())
            .first())
    if last and last.vertrag_nr:
        try:
            n = int(last.vertrag_nr.split('-')[-1]) + 1
        except ValueError:
            n = 1
    else:
        n = 1
    return f'PV-{year}-{n:03d}'


def _get(vertrag_id):
    return Pflegevertrag.query.filter_by(
        id=vertrag_id, company_id=current_user.company_id
    ).first_or_404()


# ── Übersicht ─────────────────────────────────────────────────

@pflegevertrag_bp.route('/')
@login_required
def index():
    status_filter  = request.args.get('status', '')
    patient_filter = request.args.get('patient_id', '')

    q = Pflegevertrag.query.filter_by(company_id=current_user.company_id)
    if status_filter:
        q = q.filter_by(status=status_filter)
    if patient_filter:
        q = q.filter_by(patient_id=patient_filter)

    vertraege = q.order_by(Pflegevertrag.created_at.desc()).all()
    patients  = (Patient.query
                 .filter_by(company_id=current_user.company_id, deleted_at=None)
                 .order_by(Patient.nachname).all())
    today = date.today()
    return render_template('pflegevertrag/index.html',
                           vertraege=vertraege, patients=patients,
                           status_labels=STATUS_LABELS,
                           status_filter=status_filter,
                           patient_filter=patient_filter,
                           today=today)


# ── Neuer Vertrag ─────────────────────────────────────────────

@pflegevertrag_bp.route('/neu', methods=['GET', 'POST'])
@pflegevertrag_bp.route('/neu/<patient_id>', methods=['GET', 'POST'])
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
        fd = request.form
        pid = fd.get('patient_id')
        if not pid:
            flash('Bitte einen Patienten auswählen.', 'danger')
            return render_template('pflegevertrag/form.html',
                                   patients=patients, preselected=preselected,
                                   leistungsbereiche=LEISTUNGSBEREICHE)

        # Leistungen aus Formular
        leistungen = []
        bereiche   = fd.getlist('l_bereich')
        beschreib  = fd.getlist('l_beschreibung')
        stunden    = fd.getlist('l_stundensatz')
        for b, desc, satz in zip(bereiche, beschreib, stunden):
            if b:
                leistungen.append({
                    'bereich':      b,
                    'beschreibung': desc.strip(),
                    'stundensatz':  satz.strip(),
                })

        try:
            beginn = date.fromisoformat(fd.get('beginn_datum', ''))
        except ValueError:
            beginn = date.today()

        ende_raw = fd.get('ende_datum', '').strip()
        ende = date.fromisoformat(ende_raw) if ende_raw else None

        unterschrift_patient   = bool(fd.get('unterschrift_patient'))
        unterschrift_vertreter = bool(fd.get('unterschrift_vertreter'))
        unterschrift_pdl       = bool(fd.get('unterschrift_pdl'))
        alle_unterschriften    = unterschrift_patient and unterschrift_pdl

        v = Pflegevertrag(
            company_id=current_user.company_id,
            patient_id=pid,
            created_by=current_user.id,
            vertrag_nr=_next_vertrag_nr(current_user.company_id),
            abschluss_datum=date.today(),
            beginn_datum=beginn,
            ende_datum=ende,
            leistungen=json.dumps(leistungen, ensure_ascii=False),
            kuendigungsfrist_patient=fd.get('kuendigungsfrist_patient',
                                            'zum Ende des Kalendermonats').strip(),
            kuendigungsfrist_dienst=fd.get('kuendigungsfrist_dienst',
                                           '4 Wochen zum Monatsende').strip(),
            unterschrift_patient=unterschrift_patient,
            unterschrift_vertreter=unterschrift_vertreter,
            vertreter_name=fd.get('vertreter_name', '').strip() or None,
            unterschrift_pdl=unterschrift_pdl,
            unterzeichnet_am=date.today() if alle_unterschriften else None,
            status='AKTIV' if alle_unterschriften else 'ENTWURF',
            notizen=fd.get('notizen', '').strip() or None,
        )
        db.session.add(v)
        db.session.commit()
        log_action('VERTRAG_CREATED', 'pflegevertraege', v.id,
                   new_values={'patient_id': pid, 'nr': v.vertrag_nr})
        flash(f'Vertrag {v.vertrag_nr} angelegt.', 'success')
        return redirect(url_for('pflegevertrag.show', vertrag_id=v.id))

    return render_template('pflegevertrag/form.html',
                           patients=patients, preselected=preselected,
                           leistungsbereiche=LEISTUNGSBEREICHE)


# ── Ansicht ───────────────────────────────────────────────────

@pflegevertrag_bp.route('/<vertrag_id>')
@login_required
def show(vertrag_id):
    v     = _get(vertrag_id)
    today = date.today()
    return render_template('pflegevertrag/show.html', v=v,
                           status_labels=STATUS_LABELS, today=today)


# ── Aktivieren (Unterschriften nachtragen) ───────────────────

@pflegevertrag_bp.route('/<vertrag_id>/aktivieren', methods=['POST'])
@login_required
def aktivieren(vertrag_id):
    v  = _get(vertrag_id)
    fd = request.form
    v.unterschrift_patient   = bool(fd.get('unterschrift_patient'))
    v.unterschrift_vertreter = bool(fd.get('unterschrift_vertreter'))
    v.vertreter_name         = fd.get('vertreter_name', '').strip() or None
    v.unterschrift_pdl       = bool(fd.get('unterschrift_pdl'))
    if v.unterschrift_patient and v.unterschrift_pdl:
        v.status         = 'AKTIV'
        v.unterzeichnet_am = date.today()
        flash('Vertrag aktiviert.', 'success')
    else:
        flash('Unterschriften noch unvollständig — Vertrag bleibt Entwurf.', 'warning')
    db.session.commit()
    log_action('VERTRAG_AKTIVIERT', 'pflegevertraege', v.id,
               new_values={'status': v.status})
    return redirect(url_for('pflegevertrag.show', vertrag_id=vertrag_id))


# ── Kündigen ─────────────────────────────────────────────────

@pflegevertrag_bp.route('/<vertrag_id>/kuendigen', methods=['POST'])
@login_required
def kuendigen(vertrag_id):
    v  = _get(vertrag_id)
    fd = request.form
    v.status           = 'GEKUENDIGT'
    v.kuendigung_datum = date.today()
    v.kuendigung_durch = fd.get('kuendigung_durch', 'DIENST')
    v.kuendigung_grund = fd.get('kuendigung_grund', '').strip() or None
    db.session.commit()
    log_action('VERTRAG_GEKUENDIGT', 'pflegevertraege', v.id,
               new_values={'kuendigung_durch': v.kuendigung_durch})
    flash('Vertrag als gekündigt markiert.', 'warning')
    return redirect(url_for('pflegevertrag.show', vertrag_id=vertrag_id))


# ── PDF ───────────────────────────────────────────────────────

@pflegevertrag_bp.route('/<vertrag_id>/pdf')
@login_required
def pdf(vertrag_id):
    v       = _get(vertrag_id)
    company = Company.query.get(current_user.company_id)
    try:
        from app.utils.pdf import generate_pflegevertrag_pdf
        buf      = generate_pflegevertrag_pdf(v, company)
        name     = v.patient.full_name.replace(' ', '_')
        filename = f'Pflegevertrag_{name}_{v.vertrag_nr}.pdf'
        return send_file(buf, mimetype='application/pdf',
                         as_attachment=False, download_name=filename)
    except Exception as e:
        current_app.logger.error(f'Pflegevertrag PDF error: {e}')
        flash('PDF-Erstellung fehlgeschlagen.', 'danger')
        return redirect(url_for('pflegevertrag.show', vertrag_id=vertrag_id))
