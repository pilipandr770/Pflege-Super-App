from datetime import datetime, timedelta
from flask import Blueprint, render_template, redirect, url_for, flash, request, session
from flask_login import login_user, logout_user, login_required, current_user
from app.extensions import db, bcrypt, csrf
from app.models import Employee, Company
from app.utils.auth import log_action

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', methods=['GET', 'POST'])
@csrf.exempt
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))

    error = None
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')

        employee = Employee.query.filter_by(email=email, deleted_at=None).first()

        if not employee or not employee.check_password(password):
            error = 'E-Mail oder Passwort falsch.'
            log_action('LOGIN_FAILED', 'employee')
        elif not employee.is_active:
            error = 'Ihr Konto ist deaktiviert. Bitte wenden Sie sich an Ihren Administrator.'
        else:
            is_first_login = employee.last_login_at is None
            login_user(employee, remember=False)
            employee.last_login_at = datetime.utcnow()
            db.session.commit()
            log_action('LOGIN_SUCCESS', 'employee', entity_id=employee.id)

            next_page = request.args.get('next')
            if next_page and next_page.startswith('/'):
                return redirect(next_page)

            if employee.is_superadmin:
                return redirect(url_for('superadmin.index'))

            if is_first_login:
                return redirect(url_for('dashboard.index', _anchor='onboarding'))
            return redirect(url_for('dashboard.index'))

    return render_template('auth/login.html', error=error)


@auth_bp.route('/logout')
@login_required
def logout():
    log_action('LOGOUT', 'employee', entity_id=current_user.id)
    logout_user()
    flash('Sie wurden erfolgreich abgemeldet.', 'info')
    return redirect(url_for('auth.login'))


@auth_bp.route('/register', methods=['GET', 'POST'])
@csrf.exempt
def register():
    """Регистрация новой Pflegeeinrichtung."""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))

    errors = {}
    form_data = {}

    if request.method == 'POST':
        form_data = request.form.to_dict()

        # Валидация
        required = ['company_name', 'company_type', 'strasse', 'hausnummer',
                    'plz', 'ort', 'bundesland', 'company_email',
                    'admin_vorname', 'admin_nachname', 'admin_email',
                    'password', 'password2']

        for field in required:
            if not form_data.get(field, '').strip():
                errors[field] = 'Pflichtfeld'

        if form_data.get('password') != form_data.get('password2'):
            errors['password2'] = 'Passwörter stimmen nicht überein'

        if len(form_data.get('password', '')) < 8:
            errors['password'] = 'Mindestens 8 Zeichen'

        if not form_data.get('agb'):
            errors['agb'] = 'Bitte akzeptieren Sie die AGB und Datenschutzerklärung'

        if Employee.query.filter_by(email=form_data.get('admin_email', '').lower()).first():
            errors['admin_email'] = 'Diese E-Mail ist bereits registriert'

        if Company.query.filter_by(email=form_data.get('company_email', '').lower()).first():
            errors['company_email'] = 'Diese E-Mail ist bereits registriert'

        if not errors:
            # Создаём компанию
            import re
            base_slug = re.sub(r'[^a-z0-9]', '-', form_data['company_name'].lower())[:50]

            # Проверяем уникальность slug
            slug = base_slug
            counter = 1
            while Company.query.filter_by(slug=slug).first():
                slug = f"{base_slug}-{counter}"
                counter += 1

            company = Company(
                name=form_data['company_name'].strip(),
                rechtsform=form_data.get('rechtsform', '').strip(),
                company_type=form_data['company_type'],
                strasse=form_data['strasse'].strip(),
                hausnummer=form_data['hausnummer'].strip(),
                plz=form_data['plz'].strip(),
                ort=form_data['ort'].strip(),
                bundesland=form_data['bundesland'].strip(),
                email=form_data['company_email'].strip().lower(),
                telefon=form_data.get('company_telefon', '').strip(),
                handelsregister_nr=form_data.get('handelsregister_nr', '').strip(),
                ik_nummer=form_data.get('ik_nummer', '').strip(),
                plaetze_anzahl=int(form_data['plaetze_anzahl']) if form_data.get('plaetze_anzahl') else None,
                geschaeftsfuehrer_name=form_data.get('geschaeftsfuehrer_name', '').strip(),
                pdl_name=form_data.get('pdl_name', '').strip(),
                slug=slug,
                status='PENDING',
                plan='TRIAL',
                trial_ends_at=datetime.utcnow() + timedelta(days=7),
            )
            db.session.add(company)
            db.session.flush()

            # Создаём первого сотрудника-администратора
            admin = Employee(
                company_id=company.id,
                vorname=form_data['admin_vorname'].strip(),
                nachname=form_data['admin_nachname'].strip(),
                email=form_data['admin_email'].strip().lower(),
                telefon=form_data.get('admin_telefon', '').strip(),
                role='ADMIN',
                is_active=True,
            )
            admin.set_password(form_data['password'])
            db.session.add(admin)
            db.session.commit()

            log_action('COMPANY_REGISTERED', 'company', entity_id=company.id)

            # Auto-Login des neuen Admins
            login_user(admin, remember=False)
            admin.last_login_at = datetime.utcnow()
            db.session.commit()

            # Direkt zu Stripe Checkout für 7-Tage-Trial
            return redirect(url_for('billing.onboarding'))

    bundeslaender = [
        'Baden-Württemberg', 'Bayern', 'Berlin', 'Brandenburg', 'Bremen',
        'Hamburg', 'Hessen', 'Mecklenburg-Vorpommern', 'Niedersachsen',
        'Nordrhein-Westfalen', 'Rheinland-Pfalz', 'Saarland', 'Sachsen',
        'Sachsen-Anhalt', 'Schleswig-Holstein', 'Thüringen'
    ]

    return render_template('auth/register.html',
                           errors=errors,
                           form_data=form_data,
                           bundeslaender=bundeslaender)
