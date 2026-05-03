from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app.extensions import db
from app.models import Company, Employee
from app.utils.auth import log_action, admin_required
from datetime import datetime

company_bp = Blueprint('company', __name__)


@company_bp.route('/settings', methods=['GET', 'POST'])
@login_required
@admin_required
def settings():
    company = Company.query.get_or_404(current_user.company_id)

    if request.method == 'POST':
        fd = request.form
        company.name = fd.get('name', '').strip()
        company.rechtsform = fd.get('rechtsform', '').strip()
        company.strasse = fd.get('strasse', '').strip()
        company.hausnummer = fd.get('hausnummer', '').strip()
        company.plz = fd.get('plz', '').strip()
        company.ort = fd.get('ort', '').strip()
        company.bundesland = fd.get('bundesland', '').strip()
        company.telefon = fd.get('telefon', '').strip()
        company.website = fd.get('website', '').strip()
        company.geschaeftsfuehrer_name = fd.get('geschaeftsfuehrer_name', '').strip()
        company.pdl_name = fd.get('pdl_name', '').strip()
        company.datenschutz_name = fd.get('datenschutz_name', '').strip()
        company.datenschutz_email = fd.get('datenschutz_email', '').strip()
        company.ik_nummer = fd.get('ik_nummer', '').strip()
        db.session.commit()
        log_action('UPDATE', 'companies', entity_id=company.id)
        flash('Einstellungen gespeichert.', 'success')
        return redirect(url_for('company.settings'))

    return render_template('company/settings.html', company=company)


@company_bp.route('/employees')
@login_required
@admin_required
def employees():
    staff = Employee.query.filter_by(
        company_id=current_user.company_id, deleted_at=None
    ).order_by(Employee.nachname).all()
    return render_template('company/employees.html', employees=staff)


@company_bp.route('/employees/new', methods=['GET', 'POST'])
@login_required
@admin_required
def new_employee():
    errors = {}

    if request.method == 'POST':
        fd = request.form
        if Employee.query.filter_by(email=fd.get('email', '').lower()).first():
            errors['email'] = 'Diese E-Mail existiert bereits'

        if not errors:
            emp = Employee(
                company_id=current_user.company_id,
                vorname=fd.get('vorname', '').strip(),
                nachname=fd.get('nachname', '').strip(),
                email=fd.get('email', '').strip().lower(),
                telefon=fd.get('telefon', '').strip(),
                role=fd.get('role', 'PFLEGEHILFSKRAFT'),
                qualification=fd.get('qualification', '').strip() or None,
                can_administer_btm='can_btm' in fd,
                can_wound_care='can_wound' in fd,
                can_approve_documents='can_approve' in fd,
                is_active=True,
            )
            emp.set_password(fd.get('password', 'changeme123'))
            if fd.get('pin'):
                emp.set_pin(fd.get('pin'))
            db.session.add(emp)
            db.session.commit()
            log_action('CREATE', 'employees', entity_id=emp.id)
            flash(f'Mitarbeiter {emp.full_name} angelegt.', 'success')
            return redirect(url_for('company.employees'))

    return render_template('company/employee_form.html', errors=errors, employee=None)
