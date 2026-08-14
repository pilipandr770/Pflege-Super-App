"""
Tests für company.py — Einstellungen, Mitarbeiter-CRUD, Deaktivierung.
"""
import pytest
from app.extensions import db as _db
from app.models import Employee, Company
from tests.conftest import make_company, make_employee, login, logout


# ─── Hilfs-Fixtures ──────────────────────────────────────────────────────────

@pytest.fixture
def company(db):
    return make_company()


@pytest.fixture
def admin(db, company):
    return make_employee(company, role='ADMIN',
                         vorname='Admin', nachname='Boss',
                         email='admin@test.de')


@pytest.fixture
def nurse(db, company):
    return make_employee(company, role='PFLEGEFACHKRAFT',
                         vorname='Nurse', nachname='Anna',
                         email='nurse@test.de')


@pytest.fixture
def admin_client(client, admin):
    login(client, admin.email)
    yield client
    logout(client)


@pytest.fixture
def nurse_client(client, nurse):
    login(client, nurse.email)
    yield client
    logout(client)


# ─── Einstellungen ────────────────────────────────────────────────────────────

class TestSettings:
    def test_get_settings_as_admin(self, admin_client):
        r = admin_client.get('/settings')
        assert r.status_code == 200

    def test_get_settings_forbidden_for_nurse(self, nurse_client):
        r = nurse_client.get('/settings')
        assert r.status_code in (403, 302)

    def test_update_settings(self, admin_client, company):
        r = admin_client.post('/settings', data={
            'name': 'Neuer Name GmbH',
            'rechtsform': 'GmbH',
            'strasse': 'Hauptstraße',
            'hausnummer': '42',
            'plz': '10115',
            'ort': 'Berlin',
            'bundesland': 'Berlin',
            'telefon': '030123456',
            'website': 'https://example.de',
            'geschaeftsfuehrer_name': 'Max Muster',
            'pdl_name': 'Erika PDL',
            'datenschutz_name': 'DSB Muster',
            'datenschutz_email': 'dsb@example.de',
            'ik_nummer': '123456789',
        }, follow_redirects=True)
        assert r.status_code == 200
        c = Company.query.get(company.id)
        assert c.name == 'Neuer Name GmbH'
        assert c.ort == 'Berlin'


# ─── Mitarbeiterliste ─────────────────────────────────────────────────────────

class TestEmployeeList:
    def test_list_employees_admin(self, admin_client):
        r = admin_client.get('/employees')
        assert r.status_code == 200

    def test_list_forbidden_for_nurse(self, nurse_client):
        r = nurse_client.get('/employees')
        assert r.status_code in (403, 302)

    def test_superadmin_not_listed(self, admin_client, company):
        sa = make_employee(company, role='ADMIN', email='super@test.de')
        sa.is_superadmin = True
        _db.session.commit()
        r = admin_client.get('/employees')
        assert b'super@test.de' not in r.data


# ─── Mitarbeiter anlegen ──────────────────────────────────────────────────────

class TestNewEmployee:
    def _post(self, client, **overrides):
        data = {
            'vorname': 'Lisa',
            'nachname': 'Neu',
            'email': 'lisa.neu@test.de',
            'role': 'PFLEGEHILFSKRAFT',
            'password': 'Secret123!',
            'pin': '9999',
        }
        data.update(overrides)
        return client.post('/employees/new', data=data, follow_redirects=True)

    def test_create_employee_success(self, admin_client, company):
        r = self._post(admin_client)
        assert r.status_code == 200
        emp = Employee.query.filter_by(
            company_id=company.id, email='lisa.neu@test.de'
        ).first()
        assert emp is not None
        assert emp.nachname == 'Neu'
        assert emp.role == 'PFLEGEHILFSKRAFT'

    def test_create_employee_duplicate_email(self, admin_client, nurse):
        r = self._post(admin_client, email=nurse.email)
        assert b'bereits vorhanden' in r.data or r.status_code == 200
        count = Employee.query.filter_by(email=nurse.email).count()
        assert count == 1

    def test_create_employee_empty_email(self, admin_client):
        r = self._post(admin_client, email='')
        assert r.status_code == 200
        assert Employee.query.filter_by(email='').count() == 0

    def test_create_forbidden_for_nurse(self, nurse_client):
        r = self._post(nurse_client)
        assert r.status_code in (403, 302)

    def test_password_is_hashed(self, admin_client, company):
        self._post(admin_client)
        emp = Employee.query.filter_by(email='lisa.neu@test.de').first()
        assert emp is not None
        assert emp.password_hash != 'Secret123!'
        assert emp.check_password('Secret123!')


# ─── Mitarbeiter bearbeiten ───────────────────────────────────────────────────

class TestEditEmployee:
    def test_get_edit_form(self, admin_client, nurse):
        r = admin_client.get(f'/employees/{nurse.id}/edit')
        assert r.status_code == 200
        assert nurse.vorname.encode() in r.data

    def test_edit_employee_name(self, admin_client, nurse):
        r = admin_client.post(f'/employees/{nurse.id}/edit', data={
            'vorname': 'Neue',
            'nachname': 'Name',
            'email': nurse.email,
            'role': nurse.role,
            'password': '',
            'pin': '',
        }, follow_redirects=True)
        assert r.status_code == 200
        emp = Employee.query.get(nurse.id)
        assert emp.vorname == 'Neue'
        assert emp.nachname == 'Name'

    def test_edit_changes_password_if_provided(self, admin_client, nurse):
        admin_client.post(f'/employees/{nurse.id}/edit', data={
            'vorname': nurse.vorname,
            'nachname': nurse.nachname,
            'email': nurse.email,
            'role': nurse.role,
            'password': 'NewPass999!',
            'pin': '',
        }, follow_redirects=True)
        emp = Employee.query.get(nurse.id)
        assert emp.check_password('NewPass999!')

    def test_edit_keeps_password_if_empty(self, admin_client, nurse):
        old_hash = nurse.password_hash
        admin_client.post(f'/employees/{nurse.id}/edit', data={
            'vorname': nurse.vorname,
            'nachname': nurse.nachname,
            'email': nurse.email,
            'role': nurse.role,
            'password': '',
            'pin': '',
        }, follow_redirects=True)
        emp = Employee.query.get(nurse.id)
        assert emp.password_hash == old_hash

    def test_edit_duplicate_email_rejected(self, admin_client, nurse, company):
        other = make_employee(company, role='FAHRER',
                              email='other@test.de')
        r = admin_client.post(f'/employees/{nurse.id}/edit', data={
            'vorname': nurse.vorname,
            'nachname': nurse.nachname,
            'email': other.email,
            'role': nurse.role,
            'password': '',
            'pin': '',
        }, follow_redirects=True)
        assert r.status_code == 200
        emp = Employee.query.get(nurse.id)
        assert emp.email == nurse.email  # unverändert

    def test_edit_forbidden_for_nurse(self, nurse_client, nurse):
        r = nurse_client.get(f'/employees/{nurse.id}/edit')
        assert r.status_code in (403, 302)


# ─── Mitarbeiter deaktivieren / reaktivieren ─────────────────────────────────

class TestToggleEmployee:
    def test_deactivate_employee(self, admin_client, nurse):
        assert nurse.is_active is True
        r = admin_client.post(f'/employees/{nurse.id}/toggle',
                              follow_redirects=True)
        assert r.status_code == 200
        emp = Employee.query.get(nurse.id)
        assert emp.is_active is False

    def test_reactivate_employee(self, admin_client, nurse):
        nurse.is_active = False
        _db.session.commit()
        admin_client.post(f'/employees/{nurse.id}/toggle',
                          follow_redirects=True)
        emp = Employee.query.get(nurse.id)
        assert emp.is_active is True

    def test_cannot_deactivate_self(self, admin_client, admin):
        r = admin_client.post(f'/employees/{admin.id}/toggle',
                              follow_redirects=True)
        assert r.status_code == 200
        emp = Employee.query.get(admin.id)
        assert emp.is_active is True  # bleibt aktiv

    def test_toggle_forbidden_for_nurse(self, nurse_client, nurse):
        r = nurse_client.post(f'/employees/{nurse.id}/toggle',
                              follow_redirects=True)
        assert r.status_code in (403, 200)
        emp = Employee.query.get(nurse.id)
        assert emp.is_active is True  # unverändert

    def test_toggle_cross_company_rejected(self, client, admin, company):
        other_company = make_company(name='Andere GmbH',
                                     email='other@other.de')
        other_emp = make_employee(other_company, role='PFLEGEHILFSKRAFT',
                                  email='fremder@test.de')
        login(client, admin.email)
        r = client.post(f'/employees/{other_emp.id}/toggle',
                        follow_redirects=True)
        assert r.status_code in (403, 404)
        logout(client)
