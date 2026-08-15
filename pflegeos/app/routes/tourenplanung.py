"""
Tourenplanung — Tägliche Routenplanung für ambulante Pflegedienste.

Jede Tour enthält geordnete Patientenbesuche mit Zeiten und Status.
"""
import json
from datetime import date, datetime, time
from flask import (Blueprint, render_template, redirect, url_for,
                   flash, request, jsonify, send_file, current_app, abort)
from flask_login import login_required, current_user
from app.extensions import db
from app.models import Tour, TourStop, Employee, Patient, Company
from app.utils.auth import log_action

tourenplanung_bp = Blueprint('tourenplanung', __name__, url_prefix='/touren')

STATUS_LABELS = {
    'GEPLANT':      ('Geplant',      'secondary'),
    'AKTIV':        ('Aktiv',        'primary'),
    'ABGESCHLOSSEN':('Abgeschlossen','success'),
    'ABGEBROCHEN':  ('Abgebrochen',  'danger'),
}

STOP_STATUS = {
    'GEPLANT':      ('Geplant',      'secondary'),
    'ERLEDIGT':     ('Erledigt',     'success'),
    'UEBERSPRUNGEN':('Übersprungen', 'warning'),
}


def _next_tour_nr(company_id):
    year = date.today().year
    count = Tour.query.filter(
        Tour.company_id == company_id,
        db.extract('year', Tour.datum) == year,
    ).count()
    return f'T-{year}-{count + 1:03d}'


def _get_tour(tour_id):
    return Tour.query.filter_by(
        id=tour_id, company_id=current_user.company_id
    ).first_or_404()


def _parse_time(s):
    """Parst HH:MM-String zu time-Objekt oder None."""
    if not s or not s.strip():
        return None
    try:
        return datetime.strptime(s.strip(), '%H:%M').time()
    except ValueError:
        return None


# ── Übersicht (Tages-/Wochenansicht) ─────────────────────────

@tourenplanung_bp.route('/')
@login_required
def index():
    datum_str = request.args.get('datum', date.today().isoformat())
    try:
        tag = date.fromisoformat(datum_str)
    except ValueError:
        tag = date.today()

    employee_filter = request.args.get('employee_id', '')

    q = Tour.query.filter_by(company_id=current_user.company_id, datum=tag)
    if employee_filter:
        q = q.filter_by(employee_id=employee_filter)
    touren = q.order_by(Tour.start_zeit).all()

    employees = (Employee.query
                 .filter_by(company_id=current_user.company_id, is_active=True, deleted_at=None)
                 .order_by(Employee.nachname).all())

    # Wochenkalender: 7 Tage ab Montag der aktuellen Woche
    from datetime import timedelta
    montag = tag - timedelta(days=tag.weekday())
    woche  = [montag + timedelta(days=i) for i in range(7)]

    return render_template('tourenplanung/index.html',
                           touren=touren,
                           employees=employees,
                           tag=tag,
                           woche=woche,
                           prev_week=(tag - timedelta(days=7)).isoformat(),
                           next_week=(tag + timedelta(days=7)).isoformat(),
                           employee_filter=employee_filter,
                           status_labels=STATUS_LABELS)


# ── Neue Tour anlegen ─────────────────────────────────────────

@tourenplanung_bp.route('/neu', methods=['GET', 'POST'])
@tourenplanung_bp.route('/neu/<datum>', methods=['GET', 'POST'])
@login_required
def new(datum=None):
    employees = (Employee.query
                 .filter_by(company_id=current_user.company_id, is_active=True, deleted_at=None)
                 .order_by(Employee.nachname).all())
    patients = (Patient.query
                .filter_by(company_id=current_user.company_id, status='AKTIV')
                .order_by(Patient.nachname).all())

    initial_datum = datum or date.today().isoformat()

    if request.method == 'POST':
        fd = request.form
        emp_id = fd.get('employee_id', '').strip()
        if not emp_id:
            flash('Bitte einen Mitarbeiter auswählen.', 'danger')
            return render_template('tourenplanung/form.html',
                                   employees=employees, patients=patients,
                                   initial_datum=initial_datum)
        try:
            tour_datum = date.fromisoformat(fd.get('datum', ''))
        except ValueError:
            tour_datum = date.today()

        tour = Tour(
            company_id=current_user.company_id,
            employee_id=emp_id,
            created_by=current_user.id,
            tour_nr=_next_tour_nr(current_user.company_id),
            datum=tour_datum,
            start_zeit=_parse_time(fd.get('start_zeit', '')),
            end_zeit=_parse_time(fd.get('end_zeit', '')),
            kfz_nr=fd.get('kfz_nr', '').strip() or None,
            notizen=fd.get('notizen', '').strip() or None,
        )
        db.session.add(tour)
        db.session.flush()   # get tour.id

        # Stops aus dem Formular auslesen
        patient_ids   = fd.getlist('stop_patient_id')
        ankunft_times = fd.getlist('stop_ankunft')
        dauern        = fd.getlist('stop_dauer')

        for i, pid in enumerate(patient_ids):
            if not pid:
                continue
            stop = TourStop(
                tour_id=tour.id,
                patient_id=pid,
                reihenfolge=i,
                geplante_ankunft=_parse_time(ankunft_times[i] if i < len(ankunft_times) else ''),
                geplante_dauer=int(dauern[i]) if i < len(dauern) and dauern[i].isdigit() else 30,
            )
            db.session.add(stop)

        db.session.commit()
        log_action('TOUR_CREATED', 'touren', tour.id,
                   new_values={'datum': str(tour_datum), 'employee_id': emp_id})
        flash(f'Tour {tour.tour_nr} angelegt.', 'success')
        return redirect(url_for('tourenplanung.show', tour_id=tour.id))

    return render_template('tourenplanung/form.html',
                           employees=employees, patients=patients,
                           initial_datum=initial_datum)


# ── Tour-Ansicht ──────────────────────────────────────────────

@tourenplanung_bp.route('/<tour_id>')
@login_required
def show(tour_id):
    tour = _get_tour(tour_id)
    patients = (Patient.query
                .filter_by(company_id=current_user.company_id, status='AKTIV')
                .order_by(Patient.nachname).all())
    return render_template('tourenplanung/show.html',
                           tour=tour,
                           patients=patients,
                           status_labels=STATUS_LABELS,
                           stop_status=STOP_STATUS)


# ── Stop hinzufügen (HTMX POST) ──────────────────────────────

@tourenplanung_bp.route('/<tour_id>/stop/add', methods=['POST'])
@login_required
def add_stop(tour_id):
    tour = _get_tour(tour_id)
    pid = request.form.get('patient_id', '').strip()
    if not pid:
        flash('Kein Patient ausgewählt.', 'danger')
        return redirect(url_for('tourenplanung.show', tour_id=tour_id))
    next_pos = max((s.reihenfolge for s in tour.stops), default=-1) + 1
    stop = TourStop(
        tour_id=tour.id,
        patient_id=pid,
        reihenfolge=next_pos,
        geplante_ankunft=_parse_time(request.form.get('geplante_ankunft', '')),
        geplante_dauer=int(request.form.get('geplante_dauer') or 30),
    )
    db.session.add(stop)
    db.session.commit()
    flash('Besuch hinzugefügt.', 'success')
    return redirect(url_for('tourenplanung.show', tour_id=tour_id))


# ── Stop-Status setzen ────────────────────────────────────────

@tourenplanung_bp.route('/stop/<stop_id>/status', methods=['POST'])
@login_required
def stop_status(stop_id):
    stop = TourStop.query.join(Tour).filter(
        TourStop.id == stop_id,
        Tour.company_id == current_user.company_id
    ).first_or_404()
    new_s = request.form.get('status')
    if new_s in STOP_STATUS:
        stop.status = new_s
        stop.tatsaechliche_ankunft = _parse_time(
            request.form.get('tatsaechliche_ankunft', ''))
        raw_dauer = request.form.get('tatsaechliche_dauer', '').strip()
        stop.tatsaechliche_dauer = int(raw_dauer) if raw_dauer.isdigit() else None
        stop.notizen = request.form.get('notizen', '').strip() or stop.notizen
        db.session.commit()
    return redirect(url_for('tourenplanung.show', tour_id=stop.tour_id))


# ── Stop löschen ──────────────────────────────────────────────

@tourenplanung_bp.route('/stop/<stop_id>/loeschen', methods=['POST'])
@login_required
def delete_stop(stop_id):
    stop = TourStop.query.join(Tour).filter(
        TourStop.id == stop_id,
        Tour.company_id == current_user.company_id
    ).first_or_404()
    tour_id = stop.tour_id
    db.session.delete(stop)
    db.session.commit()
    flash('Besuch entfernt.', 'info')
    return redirect(url_for('tourenplanung.show', tour_id=tour_id))


# ── Reihenfolge speichern (AJAX) ──────────────────────────────

@tourenplanung_bp.route('/<tour_id>/reorder', methods=['POST'])
@login_required
def reorder(tour_id):
    tour = _get_tour(tour_id)
    data = request.get_json(silent=True) or {}
    order = data.get('order', [])   # list of stop IDs
    for i, sid in enumerate(order):
        for s in tour.stops:
            if s.id == sid:
                s.reihenfolge = i
                break
    db.session.commit()
    return jsonify({'ok': True})


# ── Tour-Status setzen ────────────────────────────────────────

@tourenplanung_bp.route('/<tour_id>/status', methods=['POST'])
@login_required
def set_status(tour_id):
    tour = _get_tour(tour_id)
    new_s = request.form.get('status')
    if new_s in STATUS_LABELS:
        tour.status = new_s
        db.session.commit()
        flash(f'Status: {STATUS_LABELS[new_s][0]}', 'success')
    return redirect(url_for('tourenplanung.show', tour_id=tour_id))


# ── Tourenzettel PDF ──────────────────────────────────────────

@tourenplanung_bp.route('/<tour_id>.pdf')
@login_required
def tourenzettel_pdf(tour_id):
    tour    = _get_tour(tour_id)
    company = Company.query.get(current_user.company_id)
    try:
        from app.utils.pdf import generate_tourenzettel_pdf
        buf   = generate_tourenzettel_pdf(tour, company)
        fname = (f'Tour_{tour.tour_nr}_{tour.datum.strftime("%Y%m%d")}_'
                 f'{tour.employee.full_name.replace(" ", "_")}.pdf')
        return send_file(buf, mimetype='application/pdf',
                         as_attachment=False, download_name=fname)
    except Exception as e:
        current_app.logger.error(f'Tour PDF error: {e}')
        flash('PDF-Erstellung fehlgeschlagen.', 'danger')
        return redirect(url_for('tourenplanung.show', tour_id=tour_id))
