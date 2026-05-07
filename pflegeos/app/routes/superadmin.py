"""
SuperAdmin — Platform-weite Verwaltung.
Nur für Benutzer mit is_superadmin=True zugänglich.

Features:
  - Übersicht aller Einrichtungen (Unternehmen)
  - Abonnement-Status und Zahlungshistorie
  - Als Company-Admin einloggen (Impersonation)
  - Zurück zum Superadmin-Konto
  - Fuhrpark-Schnellübersicht
"""
from datetime import datetime, date, timedelta
from decimal import Decimal
from flask import (Blueprint, render_template, redirect, url_for,
                   flash, request, session, abort)
from flask_login import login_required, current_user, login_user
from app.extensions import db
from app.models import Company, Employee, Patient, Fahrzeug, SubscriptionPayment
from app.utils.auth import log_action

superadmin_bp = Blueprint('superadmin', __name__, url_prefix='/superadmin')


def _require_superadmin():
    if not current_user.is_authenticated or not current_user.is_superadmin:
        abort(403)


# ─── Übersicht ────────────────────────────────────────────────

@superadmin_bp.route('/')
@login_required
def index():
    _require_superadmin()

    companies = Company.query.filter_by(deleted_at=None).order_by(Company.created_at.desc()).all()

    stats = []
    for c in companies:
        emp_count     = Employee.query.filter_by(company_id=c.id, deleted_at=None, is_active=True).count()
        patient_count = Patient.query.filter_by(company_id=c.id, deleted_at=None, status='AKTIV').count()
        fahrzeug_count = Fahrzeug.query.filter_by(company_id=c.id, deleted_at=None).count()
        last_payment  = SubscriptionPayment.query.filter_by(
            company_id=c.id, status='PAID'
        ).order_by(SubscriptionPayment.paid_at.desc()).first()

        stats.append({
            'company':       c,
            'employees':     emp_count,
            'patients':      patient_count,
            'fahrzeuge':     fahrzeug_count,
            'last_payment':  last_payment,
        })

    total_revenue_month = db.session.query(
        db.func.sum(SubscriptionPayment.betrag)
    ).filter(
        SubscriptionPayment.status == 'PAID',
        SubscriptionPayment.paid_at >= date.today().replace(day=1),
    ).scalar() or Decimal('0')

    return render_template('superadmin/index.html',
                           stats=stats,
                           total_revenue_month=total_revenue_month)


# ─── Company Detail ───────────────────────────────────────────

@superadmin_bp.route('/company/<company_id>')
@login_required
def company_detail(company_id):
    _require_superadmin()

    c = Company.query.get_or_404(company_id)
    employees  = Employee.query.filter_by(company_id=c.id, deleted_at=None).order_by(Employee.nachname).all()
    patients   = Patient.query.filter_by(company_id=c.id, deleted_at=None).order_by(Patient.nachname).all()
    fahrzeuge  = Fahrzeug.query.filter_by(company_id=c.id, deleted_at=None).order_by(Fahrzeug.kennzeichen).all()
    payments   = SubscriptionPayment.query.filter_by(company_id=c.id).order_by(
        SubscriptionPayment.period_start.desc()
    ).limit(24).all()

    return render_template('superadmin/company_detail.html',
                           c=c,
                           employees=employees,
                           patients=patients,
                           fahrzeuge=fahrzeuge,
                           payments=payments,
                           today=date.today())


# ─── Company settings bearbeiten ─────────────────────────────

@superadmin_bp.route('/company/<company_id>/edit', methods=['GET', 'POST'])
@login_required
def company_edit(company_id):
    _require_superadmin()
    c = Company.query.get_or_404(company_id)

    if request.method == 'POST':
        fd = request.form
        c.name    = fd.get('name', c.name).strip()
        c.status  = fd.get('status', c.status)
        c.plan    = fd.get('plan', c.plan)
        if fd.get('trial_ends_at'):
            try:
                c.trial_ends_at = datetime.strptime(fd['trial_ends_at'], '%Y-%m-%d')
            except ValueError:
                pass
        db.session.commit()
        flash(f'Einrichtung „{c.name}" aktualisiert.', 'success')
        return redirect(url_for('superadmin.company_detail', company_id=c.id))

    return render_template('superadmin/company_edit.html', c=c)


# ─── Zahlung hinzufügen ───────────────────────────────────────

@superadmin_bp.route('/company/<company_id>/payment/new', methods=['POST'])
@login_required
def add_payment(company_id):
    _require_superadmin()
    c = Company.query.get_or_404(company_id)
    fd = request.form
    try:
        p = SubscriptionPayment(
            company_id=company_id,
            plan=fd.get('plan', c.plan),
            betrag=Decimal(fd.get('betrag', '0')),
            period_start=datetime.strptime(fd['period_start'], '%Y-%m-%d').date(),
            period_end=datetime.strptime(fd['period_end'], '%Y-%m-%d').date(),
            status=fd.get('status', 'PAID'),
            payment_method=fd.get('payment_method', 'BANK'),
            payment_ref=fd.get('payment_ref', '').strip(),
            rechnung_nr=fd.get('rechnung_nr', '').strip(),
            paid_at=datetime.utcnow() if fd.get('status') == 'PAID' else None,
            notiz=fd.get('notiz', '').strip(),
        )
        db.session.add(p)
        db.session.commit()
        flash('Zahlung erfasst.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Fehler: {e}', 'danger')
    return redirect(url_for('superadmin.company_detail', company_id=company_id))


# ─── Alle Zahlungen ───────────────────────────────────────────

@superadmin_bp.route('/payments')
@login_required
def payments_list():
    _require_superadmin()

    month = request.args.get('month', date.today().strftime('%Y-%m'))
    try:
        y, m = map(int, month.split('-'))
        period_start = date(y, m, 1)
        if m == 12:
            period_end = date(y + 1, 1, 1) - timedelta(days=1)
        else:
            period_end = date(y, m + 1, 1) - timedelta(days=1)
    except Exception:
        period_start = date.today().replace(day=1)
        period_end   = date.today()

    payments = SubscriptionPayment.query.filter(
        SubscriptionPayment.paid_at >= datetime.combine(period_start, datetime.min.time()),
        SubscriptionPayment.paid_at <= datetime.combine(period_end, datetime.max.time()),
    ).order_by(SubscriptionPayment.paid_at.desc()).all()

    total = sum(p.betrag for p in payments if p.status == 'PAID')

    return render_template('superadmin/payments.html',
                           payments=payments, total=total,
                           month=month, period_start=period_start)


# ─── Impersonation: Als Company-Admin einloggen ───────────────

@superadmin_bp.route('/impersonate/<company_id>')
@login_required
def impersonate(company_id):
    """Log in as the ADMIN of the target company. Stores superadmin_id in session."""
    _require_superadmin()

    target_admin = Employee.query.filter_by(
        company_id=company_id,
        role='ADMIN',
        is_active=True,
        deleted_at=None,
    ).first()

    if not target_admin:
        flash('Diese Einrichtung hat noch keinen Admin-Benutzer.', 'danger')
        return redirect(url_for('superadmin.company_detail', company_id=company_id))

    # Remember superadmin so we can switch back
    session['superadmin_id'] = current_user.id
    session['impersonating_company_name'] = target_admin.company.name

    log_action('SUPERADMIN_IMPERSONATE', 'Company', company_id,
               new_values={'target_admin': target_admin.email})

    login_user(target_admin, remember=False)
    flash(f'⚡ Sie verwalten jetzt „{target_admin.company.name}" als Admin. '
          f'<a href="/superadmin/back" class="alert-link">Zurück zu Superadmin</a>', 'warning')
    return redirect(url_for('dashboard.index'))


# ─── Zurück zum Superadmin-Konto ─────────────────────────────

@superadmin_bp.route('/back')
@login_required
def back_to_superadmin():
    """Restore superadmin login from session."""
    superadmin_id = session.pop('superadmin_id', None)
    session.pop('impersonating_company_name', None)

    if not superadmin_id:
        flash('Keine Superadmin-Sitzung gefunden.', 'warning')
        return redirect(url_for('dashboard.index'))

    superadmin = Employee.query.get(superadmin_id)
    if not superadmin or not superadmin.is_superadmin:
        flash('Superadmin-Konto nicht gefunden.', 'danger')
        return redirect(url_for('auth.login'))

    login_user(superadmin, remember=False)
    flash('Willkommen zurück im Superadmin-Panel.', 'success')
    return redirect(url_for('superadmin.index'))
