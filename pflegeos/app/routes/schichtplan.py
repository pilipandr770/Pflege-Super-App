"""
Schichtplanung — monatlicher Dienstplan für alle Mitarbeiter.
Admin: vollständige Verwaltung (Eintragen, Bearbeiten, Löschen).
Mitarbeiter: eigenen Plan lesen.
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, jsonify
from flask_login import login_required, current_user
from app.extensions import db
from app.models import Dienstschicht, Employee
from app.utils.auth import admin_required, log_action
from datetime import date, datetime, timedelta
import calendar

schichtplan_bp = Blueprint('schichtplan', __name__, url_prefix='/schichtplan')


# ── Hilfsfunktionen ──────────────────────────────────────────

def _monat_daten(year, month):
    """Gibt alle Tage des Monats als date-Liste zurück."""
    num_days = calendar.monthrange(year, month)[1]
    return [date(year, month, d) for d in range(1, num_days + 1)]


def _prev_next(year, month):
    """Berechnet Vormonat und Folgemonat."""
    if month == 1:
        prev = (year - 1, 12)
    else:
        prev = (year, month - 1)
    if month == 12:
        nxt = (year + 1, 1)
    else:
        nxt = (year, month + 1)
    return prev, nxt


def _get_schichten_map(company_id, year, month):
    """
    Lädt alle Schichten des Monats und gibt ein dict zurück:
    { employee_id: { datum: Dienstschicht } }
    """
    tage = _monat_daten(year, month)
    eintraege = Dienstschicht.query.filter_by(company_id=company_id).filter(
        Dienstschicht.datum >= tage[0],
        Dienstschicht.datum <= tage[-1]
    ).all()

    schichten_map = {}
    for s in eintraege:
        schichten_map.setdefault(s.employee_id, {})[s.datum] = s
    return schichten_map


# ── Admin: Monatsübersicht ────────────────────────────────────

@schichtplan_bp.route('/')
@login_required
@admin_required
def index():
    year  = request.args.get('year',  date.today().year,  type=int)
    month = request.args.get('month', date.today().month, type=int)
    month = max(1, min(12, month))

    cid = current_user.company_id
    tage = _monat_daten(year, month)
    prev, nxt = _prev_next(year, month)

    mitarbeiter = Employee.query.filter_by(
        company_id=cid, is_active=True, deleted_at=None
    ).filter(Employee.is_superadmin == False).order_by(
        Employee.role, Employee.nachname
    ).all()

    schichten_map = _get_schichten_map(cid, year, month)

    # Tagessummen: wie viele arbeiten an jedem Tag (Früh/Spät/Nacht)
    tages_stats = {}
    for tag in tage:
        stats = {'FRUEH': 0, 'SPAET': 0, 'NACHT': 0, 'offen': 0}
        for emp in mitarbeiter:
            s = schichten_map.get(emp.id, {}).get(tag)
            if s and s.schicht_typ in ('FRUEH', 'SPAET', 'NACHT'):
                stats[s.schicht_typ] += 1
            elif s is None:
                stats['offen'] += 1
        tages_stats[tag] = stats

    return render_template('schichtplan/index.html',
                           mitarbeiter=mitarbeiter,
                           tage=tage,
                           schichten_map=schichten_map,
                           tages_stats=tages_stats,
                           year=year, month=month,
                           prev=prev, nxt=nxt,
                           typen=Dienstschicht.TYPEN,
                           heute=date.today())


# ── Mitarbeiter: eigener Plan ─────────────────────────────────

@schichtplan_bp.route('/mein')
@login_required
def mein_plan():
    year  = request.args.get('year',  date.today().year,  type=int)
    month = request.args.get('month', date.today().month, type=int)
    month = max(1, min(12, month))

    tage = _monat_daten(year, month)
    prev, nxt = _prev_next(year, month)

    eintraege = Dienstschicht.query.filter_by(
        company_id=current_user.company_id,
        employee_id=current_user.id
    ).filter(
        Dienstschicht.datum >= tage[0],
        Dienstschicht.datum <= tage[-1]
    ).all()

    schichten = {s.datum: s for s in eintraege}

    # Statistik für den Monat
    arbeitstage  = sum(1 for s in eintraege if s.ist_arbeitstag)
    urlaub_tage  = sum(1 for s in eintraege if s.schicht_typ == 'URLAUB')
    krank_tage   = sum(1 for s in eintraege if s.schicht_typ == 'KRANK')
    frei_tage    = sum(1 for s in eintraege if s.schicht_typ == 'FREI')

    return render_template('schichtplan/mein_plan.html',
                           tage=tage,
                           schichten=schichten,
                           year=year, month=month,
                           prev=prev, nxt=nxt,
                           typen=Dienstschicht.TYPEN,
                           heute=date.today(),
                           arbeitstage=arbeitstage,
                           urlaub_tage=urlaub_tage,
                           krank_tage=krank_tage,
                           frei_tage=frei_tage)


# ── Admin: Schicht setzen (POST) ──────────────────────────────

@schichtplan_bp.route('/setzen', methods=['POST'])
@login_required
@admin_required
def setzen():
    employee_id = request.form.get('employee_id', '').strip()
    datum_str   = request.form.get('datum', '').strip()
    schicht_typ = request.form.get('schicht_typ', '').strip()
    beginn_str  = request.form.get('beginn', '').strip()
    ende_str    = request.form.get('ende', '').strip()
    bereich     = request.form.get('bereich', '').strip()
    notiz       = request.form.get('notiz', '').strip()

    # Navigationsparameter für Redirect
    year  = request.form.get('year',  type=int, default=date.today().year)
    month = request.form.get('month', type=int, default=date.today().month)

    if not employee_id or not datum_str or not schicht_typ:
        flash('Pflichtfelder fehlen.', 'danger')
        return redirect(url_for('schichtplan.index', year=year, month=month))

    if schicht_typ not in Dienstschicht.TYPEN:
        flash('Ungültiger Schichttyp.', 'danger')
        return redirect(url_for('schichtplan.index', year=year, month=month))

    # Sicherstellen, dass der Mitarbeiter zur Firma gehört
    emp = Employee.query.filter_by(
        id=employee_id, company_id=current_user.company_id
    ).first()
    if not emp:
        abort(403)

    try:
        datum = datetime.strptime(datum_str, '%Y-%m-%d').date()
    except ValueError:
        flash('Ungültiges Datum.', 'danger')
        return redirect(url_for('schichtplan.index', year=year, month=month))

    def parse_time(s):
        if not s:
            return None
        try:
            return datetime.strptime(s, '%H:%M').time()
        except ValueError:
            return None

    # Upsert: bestehenden Eintrag aktualisieren oder neu anlegen
    schicht = Dienstschicht.query.filter_by(
        company_id=current_user.company_id,
        employee_id=employee_id,
        datum=datum
    ).first()

    if schicht:
        schicht.schicht_typ = schicht_typ
        schicht.beginn  = parse_time(beginn_str)
        schicht.ende    = parse_time(ende_str)
        schicht.bereich = bereich or None
        schicht.notiz   = notiz or None
        aktion = 'SCHICHT_AKTUALISIERT'
    else:
        schicht = Dienstschicht(
            company_id  = current_user.company_id,
            employee_id = employee_id,
            datum       = datum,
            schicht_typ = schicht_typ,
            beginn      = parse_time(beginn_str),
            ende        = parse_time(ende_str),
            bereich     = bereich or None,
            notiz       = notiz or None,
            created_by  = current_user.id,
        )
        db.session.add(schicht)
        aktion = 'SCHICHT_ERSTELLT'

    db.session.commit()
    log_action(aktion, 'Dienstschicht', schicht.id, new_values={
        'employee': emp.full_name,
        'datum': datum_str,
        'typ': schicht_typ,
    })

    return redirect(url_for('schichtplan.index', year=year, month=month))


# ── Admin: Schicht löschen ────────────────────────────────────

@schichtplan_bp.route('/<schicht_id>/loeschen', methods=['POST'])
@login_required
@admin_required
def loeschen(schicht_id):
    year  = request.form.get('year',  type=int, default=date.today().year)
    month = request.form.get('month', type=int, default=date.today().month)

    schicht = Dienstschicht.query.filter_by(
        id=schicht_id, company_id=current_user.company_id
    ).first_or_404()

    log_action('SCHICHT_GELOESCHT', 'Dienstschicht', schicht_id, new_values={
        'employee_id': schicht.employee_id,
        'datum': str(schicht.datum),
        'typ': schicht.schicht_typ,
    })
    db.session.delete(schicht)
    db.session.commit()
    flash('Schichteintrag gelöscht.', 'success')
    return redirect(url_for('schichtplan.index', year=year, month=month))


# ── AJAX: Schichtdaten für Modal laden ───────────────────────

@schichtplan_bp.route('/api/schicht')
@login_required
@admin_required
def api_schicht():
    """Gibt den bestehenden Schichteintrag als JSON zurück (für Modal-Vorausfüllung)."""
    employee_id = request.args.get('employee_id', '')
    datum_str   = request.args.get('datum', '')

    if not employee_id or not datum_str:
        return jsonify({})

    try:
        datum = datetime.strptime(datum_str, '%Y-%m-%d').date()
    except ValueError:
        return jsonify({})

    schicht = Dienstschicht.query.filter_by(
        company_id=current_user.company_id,
        employee_id=employee_id,
        datum=datum
    ).first()

    if not schicht:
        return jsonify({})

    return jsonify({
        'id':          schicht.id,
        'schicht_typ': schicht.schicht_typ,
        'beginn':      schicht.beginn.strftime('%H:%M') if schicht.beginn else '',
        'ende':        schicht.ende.strftime('%H:%M')   if schicht.ende   else '',
        'bereich':     schicht.bereich or '',
        'notiz':       schicht.notiz   or '',
    })
