"""
Shared pytest fixtures for PflegeOS tests.

Uses the local Docker PostgreSQL (localhost:5432) with a dedicated
test database `pflegeos_test` that is created automatically.
CSRF is disabled for all form submissions.
"""
import re
import os
import pytest
from datetime import date, time
from decimal import Decimal

from app import create_app
from app.extensions import db as _db
from app.models import (
    Company, Employee, Patient, EmployeePatientAssignment,
    Leistungskatalog, Leistungsnachweis,
    KassenbuchEintrag,
    Fahrzeug, Kilometerbuch, Schadensmeldung, Wartungseintrag,
    MedicationPlan, Medication,
    SisAssessment, WoundDoc,
    Dienstschicht,
)


def _ensure_test_db_exists():
    """Create the pflegeos_test database on the Docker PostgreSQL if it doesn't exist."""
    import psycopg
    base = os.environ.get(
        'TEST_DATABASE_URL',
        'postgresql+psycopg://pflegeos:pflegeos_passwort@localhost:5432/pflegeos_test'
    )
    m = re.match(r'postgresql\+psycopg://([^:]+):([^@]+)@([^:/]+):?(\d+)?/(.+)', base)
    if not m:
        return
    user, password, host, port, dbname = m.groups()
    port = port or '5432'
    admin_dsn = f'host={host} port={port} dbname=postgres user={user} password={password}'
    try:
        with psycopg.connect(admin_dsn, autocommit=True) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1 FROM pg_database WHERE datname=%s", (dbname,))
                if not cur.fetchone():
                    cur.execute(f'CREATE DATABASE "{dbname}"')
    except Exception as e:
        print(f'\n[conftest] Warning: could not create test DB: {e}')


# ─── App / DB ────────────────────────────────────────────────────────────────

@pytest.fixture(scope='session')
def app():
    """One Flask app for the whole session. Tables created once."""
    _ensure_test_db_exists()
    application = create_app('testing')
    # Create schema once (no persistent app context kept here)
    with application.app_context():
        _db.create_all()
    yield application
    with application.app_context():
        _db.drop_all()


@pytest.fixture(scope='session')
def db(app):
    return _db


@pytest.fixture(autouse=True)
def app_ctx(app):
    """Push a FRESH app context for every test.

    This is the critical isolation fix: Flask's `g` is bound to the app
    context. If we reuse one long-lived app context, `g._login_user` set
    by a successful login in test N leaks into test N+1, causing
    DetachedInstanceError when Flask-Login tries to refresh the old object.
    A fresh context per test guarantees a clean `g` and a clean scoped session.
    """
    with app.app_context():
        yield
    # Exiting the context triggers teardown_appcontext → db.session.remove()


@pytest.fixture(autouse=True)
def clean_db(db, app_ctx):
    """Truncate all tables at the start of each test (runs inside app_ctx)."""
    from sqlalchemy import text, inspect as sa_inspect
    with db.engine.connect() as conn:
        inspector = sa_inspect(conn)
        tables = inspector.get_table_names()
        if tables:
            names = ', '.join(f'"{t}"' for t in tables)
            conn.execute(text(f'TRUNCATE {names} RESTART IDENTITY CASCADE'))
            conn.commit()
    yield


# ─── Helper: create objects ──────────────────────────────────────────────────

def make_company(**kwargs):
    defaults = dict(
        name='Pflegedienst Test GmbH',
        company_type='AMBULANT',
        strasse='Musterstraße',
        hausnummer='1',
        plz='10115',
        ort='Berlin',
        bundesland='Berlin',
        email='test@pflegedienst.de',
        status='ACTIVE',
        plan='PRO',
    )
    defaults.update(kwargs)
    c = Company(**defaults)
    _db.session.add(c)
    _db.session.commit()
    return c


def make_employee(company, role='ADMIN', **kwargs):
    defaults = dict(
        company_id=company.id,
        vorname='Max',
        nachname='Mustermann',
        email=f'emp_{role.lower()}_{id(kwargs)}@test.de',
        role=role,
        is_active=True,
    )
    defaults.update(kwargs)
    e = Employee(**defaults)
    e.set_password('Test1234!')
    e.set_pin('1234')
    _db.session.add(e)
    _db.session.commit()
    return e


def make_patient(company, **kwargs):
    defaults = dict(
        company_id=company.id,
        vorname='Erika',
        nachname='Musterfrau',
        pflegegrad='2',
        aufnahmedatum=date(2025, 1, 1),
        status='AKTIV',
        care_type='HOME_CARE',
        krankenversicherung='AOK Berlin',
    )
    defaults.update(kwargs)
    p = Patient(**defaults)
    _db.session.add(p)
    _db.session.commit()
    return p


def make_leistung(company, **kwargs):
    defaults = dict(
        company_id=company.id,
        bezeichnung='Grundpflege',
        leistung_nr='GP-01',
        dauer_minuten=30,
        preis=25.50,
        is_active=True,
    )
    defaults.update(kwargs)
    l = Leistungskatalog(**defaults)
    _db.session.add(l)
    _db.session.commit()
    return l


def make_schicht(company, employee, datum=None, schicht_typ='FRUEH', **kwargs):
    from datetime import time as dtime
    defaults = dict(
        company_id=company.id,
        employee_id=employee.id,
        datum=datum or date.today(),
        schicht_typ=schicht_typ,
        beginn=dtime(6, 0) if schicht_typ == 'FRUEH' else None,
        ende=dtime(14, 0) if schicht_typ == 'FRUEH' else None,
    )
    defaults.update(kwargs)
    s = Dienstschicht(**defaults)
    _db.session.add(s)
    _db.session.commit()
    return s


def make_fahrzeug(company, **kwargs):
    defaults = dict(
        company_id=company.id,
        kennzeichen='B-PF 1234',
        marke='VW',
        modell='Caddy',
        status='AKTIV',
        km_stand=50000,
    )
    defaults.update(kwargs)
    f = Fahrzeug(**defaults)
    _db.session.add(f)
    _db.session.commit()
    return f


# ─── Fixtures: pre-built objects ─────────────────────────────────────────────

@pytest.fixture
def company(db):
    return make_company()


@pytest.fixture
def admin(db, company):
    return make_employee(company, role='ADMIN',
                         vorname='Admin', nachname='User',
                         email='admin@test.de')


@pytest.fixture
def pflegefachkraft(db, company):
    return make_employee(company, role='PFLEGEFACHKRAFT',
                         vorname='Pflegefach', nachname='Kraft',
                         email='fachkraft@test.de',
                         can_wound_care=True)


@pytest.fixture
def pflegehilfskraft(db, company):
    return make_employee(company, role='PFLEGEHILFSKRAFT',
                         vorname='Pflege', nachname='Hilfe',
                         email='hilfskraft@test.de')


@pytest.fixture
def fahrer(db, company):
    return make_employee(company, role='FAHRER',
                         vorname='Fahrer', nachname='Hans',
                         email='fahrer@test.de')


@pytest.fixture
def verwaltung(db, company):
    return make_employee(company, role='VERWALTUNG',
                         vorname='Büro', nachname='Anna',
                         email='verwaltung@test.de')


@pytest.fixture
def patient(db, company):
    return make_patient(company)


@pytest.fixture
def leistung(db, company):
    return make_leistung(company)


@pytest.fixture
def fahrzeug(db, company):
    return make_fahrzeug(company)


# ─── HTTP client helpers ─────────────────────────────────────────────────────

@pytest.fixture
def client(app):
    return app.test_client()


def login(client, email, password='Test1234!'):
    """Login helper — returns the response of the POST /auth/login."""
    return client.post('/auth/login', data={
        'email': email,
        'password': password,
    }, follow_redirects=True)


def logout(client):
    return client.get('/auth/logout', follow_redirects=True)


@pytest.fixture
def admin_client(client, admin):
    login(client, admin.email)
    yield client
    logout(client)


@pytest.fixture
def fachkraft_client(client, pflegefachkraft):
    login(client, pflegefachkraft.email)
    yield client
    logout(client)


@pytest.fixture
def fahrer_client(client, fahrer):
    login(client, fahrer.email)
    yield client
    logout(client)


@pytest.fixture
def verwaltung_client(client, verwaltung):
    login(client, verwaltung.email)
    yield client
    logout(client)
