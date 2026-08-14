"""
Standort-Verwaltung: Filialen / Wohnbereiche eines Pflegedienstes.
"""
from flask import (Blueprint, render_template, redirect, url_for,
                   flash, request)
from flask_login import login_required, current_user
from app.extensions import db
from app.models import Standort, Employee
from app.utils.auth import admin_required, log_action

standorte_bp = Blueprint('standorte', __name__, url_prefix='/standorte')


@standorte_bp.route('/')
@login_required
@admin_required
def index():
    standorte = Standort.query.filter_by(
        company_id=current_user.company_id
    ).order_by(Standort.name).all()
    return render_template('standorte/index.html', standorte=standorte)


@standorte_bp.route('/neu', methods=['GET', 'POST'])
@login_required
@admin_required
def new():
    employees = Employee.query.filter_by(
        company_id=current_user.company_id, deleted_at=None, is_active=True
    ).order_by(Employee.nachname).all()

    if request.method == 'POST':
        fd = request.form
        kuerzel = fd.get('kuerzel', '').strip() or None

        # Duplikat-Check
        if kuerzel:
            existing = Standort.query.filter_by(
                company_id=current_user.company_id, kuerzel=kuerzel
            ).first()
            if existing:
                flash(f'Kürzel „{kuerzel}" ist bereits vergeben.', 'danger')
                return render_template('standorte/form.html', standort=None,
                                       employees=employees)

        s = Standort(
            company_id=current_user.company_id,
            name=fd.get('name', '').strip(),
            kuerzel=kuerzel,
            beschreibung=fd.get('beschreibung', '').strip() or None,
            strasse=fd.get('strasse', '').strip() or None,
            hausnummer=fd.get('hausnummer', '').strip() or None,
            plz=fd.get('plz', '').strip() or None,
            ort=fd.get('ort', '').strip() or None,
            telefon=fd.get('telefon', '').strip() or None,
            leiter_id=fd.get('leiter_id') or None,
        )
        db.session.add(s)
        db.session.commit()
        log_action('STANDORT_CREATED', 'standorte', s.id,
                   new_values={'name': s.name})
        flash(f'Standort „{s.name}" angelegt.', 'success')
        return redirect(url_for('standorte.index'))

    return render_template('standorte/form.html', standort=None,
                           employees=employees)


@standorte_bp.route('/<standort_id>/bearbeiten', methods=['GET', 'POST'])
@login_required
@admin_required
def edit(standort_id):
    s = _get(standort_id)
    employees = Employee.query.filter_by(
        company_id=current_user.company_id, deleted_at=None, is_active=True
    ).order_by(Employee.nachname).all()

    if request.method == 'POST':
        fd = request.form
        kuerzel = fd.get('kuerzel', '').strip() or None

        if kuerzel and kuerzel != s.kuerzel:
            existing = Standort.query.filter_by(
                company_id=current_user.company_id, kuerzel=kuerzel
            ).filter(Standort.id != standort_id).first()
            if existing:
                flash(f'Kürzel „{kuerzel}" ist bereits vergeben.', 'danger')
                return render_template('standorte/form.html', standort=s,
                                       employees=employees)

        s.name        = fd.get('name', '').strip()
        s.kuerzel     = kuerzel
        s.beschreibung = fd.get('beschreibung', '').strip() or None
        s.strasse     = fd.get('strasse', '').strip() or None
        s.hausnummer  = fd.get('hausnummer', '').strip() or None
        s.plz         = fd.get('plz', '').strip() or None
        s.ort         = fd.get('ort', '').strip() or None
        s.telefon     = fd.get('telefon', '').strip() or None
        s.leiter_id   = fd.get('leiter_id') or None
        db.session.commit()
        log_action('STANDORT_UPDATED', 'standorte', s.id,
                   new_values={'name': s.name})
        flash('Standort aktualisiert.', 'success')
        return redirect(url_for('standorte.index'))

    return render_template('standorte/form.html', standort=s,
                           employees=employees)


@standorte_bp.route('/<standort_id>/deaktivieren', methods=['POST'])
@login_required
@admin_required
def deactivate(standort_id):
    s = _get(standort_id)
    s.is_active = not s.is_active
    db.session.commit()
    status = 'aktiviert' if s.is_active else 'deaktiviert'
    log_action(f'STANDORT_{status.upper()}', 'standorte', s.id)
    flash(f'Standort „{s.name}" wurde {status}.', 'success')
    return redirect(url_for('standorte.index'))


def _get(standort_id):
    return Standort.query.filter_by(
        id=standort_id, company_id=current_user.company_id
    ).first_or_404()
