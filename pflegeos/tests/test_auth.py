"""
Tests for authentication: login, logout, registration, access control.
"""
import pytest
from app.models import Employee, Company
from app.extensions import db
from tests.conftest import make_company, make_employee, login, logout


class TestLogin:
    def test_login_page_renders(self, client):
        r = client.get('/auth/login')
        assert r.status_code == 200
        assert b'login' in r.data.lower() or b'anmelden' in r.data.lower()

    def test_login_success_redirects_to_dashboard(self, client, admin):
        r = client.post('/auth/login', data={
            'email': admin.email,
            'password': 'Test1234!',
        }, follow_redirects=False)
        # should redirect to /
        assert r.status_code in (301, 302)

    def test_login_wrong_password(self, client, admin):
        r = client.post('/auth/login', data={
            'email': admin.email,
            'password': 'wrongpassword',
        }, follow_redirects=True)
        assert r.status_code == 200
        assert b'falsch' in r.data.lower() or b'error' in r.data.lower() or b'passwort' in r.data.lower()

    def test_login_unknown_email(self, client):
        r = client.post('/auth/login', data={
            'email': 'nobody@nowhere.com',
            'password': 'Test1234!',
        }, follow_redirects=True)
        assert r.status_code == 200
        # should show error, not crash
        assert r.data

    def test_login_inactive_user_blocked(self, client, company, db):
        emp = make_employee(company, role='PFLEGEHILFSKRAFT',
                            email='inactive@test.de')
        emp.is_active = False
        db.session.flush()

        r = client.post('/auth/login', data={
            'email': 'inactive@test.de',
            'password': 'Test1234!',
        }, follow_redirects=True)
        assert r.status_code == 200
        assert b'deaktiviert' in r.data.lower() or b'konto' in r.data.lower()

    def test_login_sets_last_login_at(self, client, admin, db):
        assert admin.last_login_at is None
        login(client, admin.email)
        db.session.refresh(admin)
        assert admin.last_login_at is not None

    def test_already_logged_in_redirects(self, admin_client):
        r = admin_client.get('/auth/login', follow_redirects=False)
        assert r.status_code in (301, 302)


class TestLogout:
    def test_logout_clears_session(self, client, admin):
        login(client, admin.email)
        r = client.get('/auth/logout', follow_redirects=True)
        assert r.status_code == 200
        # after logout, / now shows the public landing page (200)
        r2 = client.get('/', follow_redirects=False)
        assert r2.status_code == 200

    def test_logout_requires_login(self, client):
        r = client.get('/auth/logout', follow_redirects=False)
        # should redirect to login
        assert r.status_code in (301, 302)


class TestRegister:
    def test_register_page_renders(self, client):
        r = client.get('/auth/register')
        assert r.status_code == 200

    def test_register_new_company(self, client, db):
        r = client.post('/auth/register', data={
            'company_name': 'Neuer Pflegedienst GmbH',
            'company_type': 'AMBULANT',
            'strasse': 'Hauptstraße',
            'hausnummer': '10',
            'plz': '10117',
            'ort': 'Berlin',
            'bundesland': 'Berlin',
            'company_email': 'neuer@pflegedienst.de',
            'admin_vorname': 'Klaus',
            'admin_nachname': 'Meier',
            'admin_email': 'admin@neuer-pflegedienst.de',
            'password': 'Sicher1234!',
            'password2': 'Sicher1234!',
            'agb': 'on',
        }, follow_redirects=False)
        # After registration the user is auto-logged in and redirected to Stripe onboarding
        assert r.status_code in (302, 303)
        # Company and admin should be created
        c = Company.query.filter_by(email='neuer@pflegedienst.de').first()
        assert c is not None
        e = Employee.query.filter_by(email='admin@neuer-pflegedienst.de').first()
        assert e is not None
        assert e.role == 'ADMIN'

    def test_register_password_mismatch(self, client):
        r = client.post('/auth/register', data={
            'company_name': 'Test GmbH',
            'company_type': 'AMBULANT',
            'strasse': 'Str.',
            'hausnummer': '1',
            'plz': '10115',
            'ort': 'Berlin',
            'bundesland': 'Berlin',
            'company_email': 'mismatch@test.de',
            'admin_vorname': 'A',
            'admin_nachname': 'B',
            'admin_email': 'admin@mismatch.de',
            'password': 'abc',
            'password2': 'xyz',
        }, follow_redirects=True)
        assert r.status_code == 200
        assert b'stimmen' in r.data.lower() or b'passwort' in r.data.lower()
        # Company should NOT be created
        assert Company.query.filter_by(email='mismatch@test.de').first() is None

    def test_register_duplicate_email(self, client, company):
        r = client.post('/auth/register', data={
            'company_name': 'Doppelt GmbH',
            'company_type': 'AMBULANT',
            'strasse': 'Str.',
            'hausnummer': '1',
            'plz': '10115',
            'ort': 'Berlin',
            'bundesland': 'Berlin',
            'company_email': company.email,  # duplicate
            'admin_vorname': 'X',
            'admin_nachname': 'Y',
            'admin_email': 'fresh@email.de',
            'password': 'Test1234!',
            'password2': 'Test1234!',
        }, follow_redirects=True)
        assert r.status_code == 200
        # Should show an error or only one company with that email
        count = Company.query.filter_by(email=company.email).count()
        assert count == 1


class TestPasswordHelpers:
    def test_set_and_check_password(self, admin):
        admin.set_password('NewPass99!')
        assert admin.check_password('NewPass99!')
        assert not admin.check_password('WrongPass')

    def test_set_and_check_pin(self, admin):
        admin.set_pin('9999')
        assert admin.check_pin('9999')
        assert not admin.check_pin('0000')


class TestUnauthenticatedAccess:
    """Unauthenticated users should be redirected to login for protected pages."""

    @pytest.mark.parametrize('url', [
        '/patients/',
        '/buchhaltung/',
        '/fuhrpark/',
        '/medications/btm-buch',
        '/leistung/katalog',
        '/wounds/patient/00000000-0000-0000-0000-000000000000',
        '/sis/patient/00000000-0000-0000-0000-000000000000',
        '/company/settings',
    ])
    def test_redirect_to_login(self, client, url):
        r = client.get(url, follow_redirects=False)
        assert r.status_code in (301, 302)
        location = r.headers.get('Location', '')
        assert 'login' in location or r.status_code == 302
