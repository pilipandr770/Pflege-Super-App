"""
Fortbildungsnachweis — Dokumentation der Mitarbeiter-Weiterbildung.

Pflichtfortbildungen und freiwillige Schulungen werden hier erfasst
und können als MDK-konforme PDF-Übersicht exportiert werden.
"""
import os
from datetime import date
from decimal import Decimal
from flask import (Blueprint, render_template, redirect, url_for,
                   flash, request, send_file, current_app, abort)
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from app.extensions import db
from app.models import Fortbildung, Employee, Company
from app.utils.auth import admin_required, log_action

fortbildung_bp = Blueprint('fortbildung', __name__, url_prefix='/fortbildung')

ALLOWED_EXT = {'pdf', 'jpg', 'jpeg', 'png'}

STATUS_LABELS = {
    'GEPLANT':     ('Geplant',     'secondary'),
    'ABSOLVIERT':  ('Absolviert',  'success'),
    'ABGEBROCHEN': ('Abgebrochen', 'danger'),
}


def _allowed(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXT


def _get(fb_id):
    return Fortbildung.query.filter_by(
        id=fb_id, company_id=current_user.company_id
    ).first_or_404()


def _save_cert(file):
    """Speichert Zertifikat und gibt relativen Pfad zurück."""
    if not file or file.filename == '':
        return None
    if not _allowed(file.filename):
        return None
    folder = os.path.join(current_app.config['UPLOAD_FOLDER'], 'fortbildungen')
    os.makedirs(folder, exist_ok=True)
    fname = secure_filename(f'{date.today().isoformat()}_{file.filename}')
    fpath = os.path.join(folder, fname)
    file.save(fpath)
    return os.path.join('fortbildungen', fname)


# ── Übersicht ─────────────────────────────────────────────────

@fortbildung_bp.route('/')
@login_required
def index():
    year_filter     = request.args.get('year', str(date.today().year))
    employee_filter = request.args.get('employee_id', '')
    thema_filter    = request.args.get('themenbereich', '')
    status_filter   = request.args.get('status', '')

    q = Fortbildung.query.filter_by(company_id=current_user.company_id)
    if year_filter:
        try:
            y = int(year_filter)
            q = q.filter(db.extract('year', Fortbildung.datum_von) == y)
        except ValueError:
            pass
    if employee_filter:
        q = q.filter_by(employee_id=employee_filter)
    if thema_filter:
        q = q.filter_by(themenbereich=thema_filter)
    if status_filter:
        q = q.filter_by(status=status_filter)

    fortbildungen = q.order_by(Fortbildung.datum_von.desc()).all()

    employees = (Employee.query
                 .filter_by(company_id=current_user.company_id, is_active=True, deleted_at=None)
                 .order_by(Employee.nachname).all())

    # KPIs
    alle_jahr = (Fortbildung.query
                 .filter_by(company_id=current_user.company_id)
                 .filter(db.extract('year', Fortbildung.datum_von) == int(year_filter or date.today().year))
                 .all())
    kpi_gesamt     = len(alle_jahr)
    kpi_absolviert = sum(1 for f in alle_jahr if f.status == 'ABSOLVIERT')
    kpi_pflicht    = sum(1 for f in alle_jahr if f.pflicht_fortbildung and f.status == 'ABSOLVIERT')
    kpi_stunden    = sum(float(f.stunden or 0) for f in alle_jahr if f.status == 'ABSOLVIERT')

    years = list(range(date.today().year, date.today().year - 5, -1))

    return render_template('fortbildung/index.html',
                           fortbildungen=fortbildungen,
                           employees=employees,
                           themen=Fortbildung.THEMEN,
                           status_labels=STATUS_LABELS,
                           year_filter=year_filter,
                           employee_filter=employee_filter,
                           thema_filter=thema_filter,
                           status_filter=status_filter,
                           kpi_gesamt=kpi_gesamt,
                           kpi_absolviert=kpi_absolviert,
                           kpi_pflicht=kpi_pflicht,
                           kpi_stunden=kpi_stunden,
                           years=years)


# ── Neue Fortbildung ──────────────────────────────────────────

@fortbildung_bp.route('/neu', methods=['GET', 'POST'])
@fortbildung_bp.route('/neu/<employee_id>', methods=['GET', 'POST'])
@login_required
def new(employee_id=None):
    employees = (Employee.query
                 .filter_by(company_id=current_user.company_id, is_active=True, deleted_at=None)
                 .order_by(Employee.nachname).all())
    preselected = None
    if employee_id:
        preselected = Employee.query.filter_by(
            id=employee_id, company_id=current_user.company_id
        ).first_or_404()

    if request.method == 'POST':
        fd  = request.form
        eid = fd.get('employee_id')
        if not eid:
            flash('Bitte einen Mitarbeiter auswählen.', 'danger')
            return render_template('fortbildung/form.html',
                                   employees=employees, preselected=preselected,
                                   themen=Fortbildung.THEMEN, today=date.today())

        try:
            datum_von = date.fromisoformat(fd.get('datum_von', ''))
        except ValueError:
            datum_von = date.today()

        datum_bis_raw = fd.get('datum_bis', '').strip()
        datum_bis = date.fromisoformat(datum_bis_raw) if datum_bis_raw else None

        kosten_raw = fd.get('kosten', '').strip().replace(',', '.')
        kosten = Decimal(kosten_raw) if kosten_raw else None

        zert_pfad = _save_cert(request.files.get('zertifikat'))

        status = fd.get('status', 'GEPLANT')
        # Wenn kein Enddatum und Datum in der Vergangenheit → automatisch ABSOLVIERT
        if not datum_bis and datum_von <= date.today() and status == 'GEPLANT':
            status = 'ABSOLVIERT'

        fb = Fortbildung(
            company_id=current_user.company_id,
            employee_id=eid,
            created_by=current_user.id,
            titel=fd.get('titel', '').strip(),
            anbieter=fd.get('anbieter', '').strip() or None,
            ort=fd.get('ort', '').strip() or None,
            datum_von=datum_von,
            datum_bis=datum_bis,
            stunden=fd.get('stunden', 8) or 8,
            themenbereich=fd.get('themenbereich', 'PFLEGE'),
            pflicht_fortbildung=bool(fd.get('pflicht_fortbildung')),
            zertifikat_pfad=zert_pfad,
            kosten=kosten,
            status=status,
            notizen=fd.get('notizen', '').strip() or None,
        )
        db.session.add(fb)
        db.session.commit()
        log_action('FORTBILDUNG_CREATED', 'fortbildungen', fb.id,
                   new_values={'employee_id': eid, 'titel': fb.titel})
        flash(f'Fortbildung „{fb.titel}" gespeichert.', 'success')
        return redirect(url_for('fortbildung.show', fb_id=fb.id))

    return render_template('fortbildung/form.html',
                           employees=employees, preselected=preselected,
                           themen=Fortbildung.THEMEN, today=date.today())


# ── Ansicht / Bearbeiten ──────────────────────────────────────

@fortbildung_bp.route('/<fb_id>')
@login_required
def show(fb_id):
    fb = _get(fb_id)
    return render_template('fortbildung/show.html', fb=fb,
                           status_labels=STATUS_LABELS)


@fortbildung_bp.route('/<fb_id>/bearbeiten', methods=['GET', 'POST'])
@login_required
def edit(fb_id):
    fb = _get(fb_id)
    employees = (Employee.query
                 .filter_by(company_id=current_user.company_id, is_active=True, deleted_at=None)
                 .order_by(Employee.nachname).all())

    if request.method == 'POST':
        fd = request.form
        try:
            fb.datum_von = date.fromisoformat(fd.get('datum_von', ''))
        except ValueError:
            pass
        datum_bis_raw = fd.get('datum_bis', '').strip()
        fb.datum_bis  = date.fromisoformat(datum_bis_raw) if datum_bis_raw else None
        fb.titel      = fd.get('titel', '').strip()
        fb.anbieter   = fd.get('anbieter', '').strip() or None
        fb.ort        = fd.get('ort', '').strip() or None
        fb.stunden    = fd.get('stunden', 8) or 8
        fb.themenbereich      = fd.get('themenbereich', 'PFLEGE')
        fb.pflicht_fortbildung = bool(fd.get('pflicht_fortbildung'))
        fb.status     = fd.get('status', 'GEPLANT')
        fb.notizen    = fd.get('notizen', '').strip() or None

        kosten_raw = fd.get('kosten', '').strip().replace(',', '.')
        fb.kosten  = Decimal(kosten_raw) if kosten_raw else None

        new_cert = request.files.get('zertifikat')
        if new_cert and new_cert.filename:
            fb.zertifikat_pfad = _save_cert(new_cert)

        db.session.commit()
        log_action('FORTBILDUNG_UPDATED', 'fortbildungen', fb.id,
                   new_values={'status': fb.status})
        flash('Fortbildung aktualisiert.', 'success')
        return redirect(url_for('fortbildung.show', fb_id=fb.id))

    return render_template('fortbildung/form.html',
                           fb=fb, employees=employees,
                           preselected=fb.employee,
                           themen=Fortbildung.THEMEN, today=date.today())


# ── Status direkt setzen ──────────────────────────────────────

@fortbildung_bp.route('/<fb_id>/status', methods=['POST'])
@login_required
def update_status(fb_id):
    fb = _get(fb_id)
    new_status = request.form.get('status')
    if new_status in STATUS_LABELS:
        fb.status = new_status
        db.session.commit()
        flash(f'Status auf „{STATUS_LABELS[new_status][0]}" gesetzt.', 'success')
    return redirect(url_for('fortbildung.show', fb_id=fb_id))


# ── PDF: Mitarbeiter-Nachweis ─────────────────────────────────

@fortbildung_bp.route('/nachweis/<employee_id>.pdf')
@login_required
def nachweis_pdf(employee_id):
    emp = Employee.query.filter_by(
        id=employee_id, company_id=current_user.company_id
    ).first_or_404()
    year = request.args.get('year', date.today().year)
    try:
        year = int(year)
    except ValueError:
        year = date.today().year

    fbs = (Fortbildung.query
           .filter_by(company_id=current_user.company_id, employee_id=employee_id)
           .filter(db.extract('year', Fortbildung.datum_von) == year)
           .order_by(Fortbildung.datum_von).all())

    company = Company.query.get(current_user.company_id)
    try:
        from app.utils.pdf import generate_fortbildungsnachweis_pdf
        buf = generate_fortbildungsnachweis_pdf(emp, fbs, year, company)
        fname = f'Fortbildungsnachweis_{emp.full_name.replace(" ", "_")}_{year}.pdf'
        return send_file(buf, mimetype='application/pdf',
                         as_attachment=False, download_name=fname)
    except Exception as e:
        current_app.logger.error(f'Fortbildung PDF error: {e}')
        flash('PDF-Erstellung fehlgeschlagen.', 'danger')
        return redirect(url_for('fortbildung.index'))


# ── CSV-Export (für MDK-Audit) ────────────────────────────────

@fortbildung_bp.route('/export.csv')
@login_required
def export_csv():
    import csv
    import io
    year = request.args.get('year', date.today().year)
    try:
        year = int(year)
    except ValueError:
        year = date.today().year

    fbs = (Fortbildung.query
           .filter_by(company_id=current_user.company_id)
           .filter(db.extract('year', Fortbildung.datum_von) == year)
           .filter_by(status='ABSOLVIERT')
           .order_by(Fortbildung.employee_id, Fortbildung.datum_von)
           .all())

    out = io.StringIO()
    w   = csv.writer(out, delimiter=';')
    w.writerow(['Mitarbeiter', 'Rolle', 'Fortbildung', 'Thema',
                'Datum', 'Stunden', 'Pflicht', 'Anbieter', 'Kosten (€)'])
    for f in fbs:
        w.writerow([
            f.employee.full_name,
            f.employee.role_label,
            f.titel,
            f.thema_label,
            f.datum_von.strftime('%d.%m.%Y'),
            str(f.stunden or ''),
            'Ja' if f.pflicht_fortbildung else 'Nein',
            f.anbieter or '',
            str(f.kosten or ''),
        ])

    out.seek(0)
    return send_file(
        io.BytesIO(out.getvalue().encode('utf-8-sig')),
        mimetype='text/csv',
        as_attachment=True,
        download_name=f'Fortbildungen_{year}.csv'
    )
