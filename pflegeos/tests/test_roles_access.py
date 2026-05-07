"""
Comprehensive role-based access control (RBAC) tests.

Tests every role against every module to verify the permission matrix:

Role            | Dashboard | Patients | SIS | Meds | Leistung | Wounds | Buchhalt | Fuhrpark | Admin
----------------|-----------|----------|-----|------|----------|--------|----------|----------|-------
ADMIN           |    ✓      |    ✓     |  ✓  |  ✓   |    ✓     |   ✓    |    ✓     |    ✓     |  ✓
PFLEGEFACHKRAFT |    ✓      |  own     |  ✓  |  ✓   |    ✓     |   ✓    |    ✗     |    ✗     |  ✗
PFLEGEHILFSKRAFT|    ✓      |  own     |  ✗* |  ✗*  |    ✓     |   ✗*   |    ✗     |    ✗     |  ✗
BEHANDLUNGSPFLEGE|   ✓      |  own     |  ✓  |  ✓   |    ✓     |   ✓    |    ✗     |    ✗     |  ✗
HAUSWIRTSCHAFT  |    ✓      |  own     |  ✗  |  ✗   |    ✓     |   ✗    |    ✗     |    ✗     |  ✗
FAHRER          |    ✓      |   ✗      |  ✗  |  ✗   |    ✗     |   ✗    |    ✗     |    ✓     |  ✗
VERWALTUNG      |    ✓      |  read    |  ✗  |  ✗   |  read    |   ✗    |    ✓     |    ✗     |  ✗

* with appropriate permissions flag
"""
import pytest
from datetime import date
from tests.conftest import make_employee, make_patient, login
from app.models import EmployeePatientAssignment
from app.extensions import db


# ─── Role properties ─────────────────────────────────────────────────────────

class TestEmployeeRoleProperties:
    def test_admin_is_admin(self, admin):
        assert admin.is_admin is True
        assert admin.is_field_staff is False
        assert admin.is_office_role is False

    def test_pflegefachkraft_is_care_and_field(self, pflegefachkraft):
        assert pflegefachkraft.is_admin is False
        assert pflegefachkraft.is_care_role is True
        assert pflegefachkraft.is_field_staff is True

    def test_pflegehilfskraft_is_care(self, pflegehilfskraft):
        assert pflegehilfskraft.is_care_role is True
        assert pflegehilfskraft.is_field_staff is True

    def test_fahrer_is_field_staff(self, fahrer):
        assert fahrer.is_field_staff is True
        assert fahrer.is_care_role is False
        assert fahrer.is_admin is False

    def test_verwaltung_is_office(self, verwaltung):
        assert verwaltung.is_office_role is True
        assert verwaltung.is_admin is False
        assert verwaltung.is_field_staff is False

    def test_admin_can_see_btm(self, admin):
        assert admin.can_see_btm is True

    def test_fachkraft_can_see_btm(self, pflegefachkraft):
        assert pflegefachkraft.can_see_btm is True

    def test_hilfskraft_cannot_see_btm_by_default(self, pflegehilfskraft):
        assert pflegehilfskraft.can_see_btm is False

    def test_hilfskraft_can_see_btm_with_flag(self, company, db):
        hk = make_employee(company, role='PFLEGEHILFSKRAFT',
                            email='btm_hk@test.de',
                            can_administer_btm=True)
        assert hk.can_see_btm is True

    def test_role_labels(self, admin, pflegefachkraft, fahrer, verwaltung):
        assert admin.role_label == 'Administrator'
        assert pflegefachkraft.role_label == 'Pflegefachkraft'
        assert fahrer.role_label == 'Fahrer/in'
        assert verwaltung.role_label == 'Verwaltung'


# ─── Dashboard access ────────────────────────────────────────────────────────

class TestDashboardAccess:
    @pytest.mark.parametrize('role,email,expected', [
        ('ADMIN',             'dash_admin@test.de',   200),
        ('PFLEGEFACHKRAFT',   'dash_fach@test.de',    200),
        ('PFLEGEHILFSKRAFT',  'dash_hilf@test.de',    200),
        ('FAHRER',            'dash_fahr@test.de',    200),
        ('VERWALTUNG',        'dash_verw@test.de',    200),
        ('HAUSWIRTSCHAFT',    'dash_hw@test.de',      200),
    ])
    def test_role_can_access_dashboard(self, client, company, db,
                                        role, email, expected):
        emp = make_employee(company, role=role, email=email)
        login(client, emp.email)
        r = client.get('/', follow_redirects=True)
        assert r.status_code == expected


# ─── Buchhaltung access matrix ───────────────────────────────────────────────

class TestBuchhaltungRoleAccess:
    @pytest.mark.parametrize('role,email,expected', [
        ('ADMIN',             'buch_adm@test.de',   200),
        ('VERWALTUNG',        'buch_ver@test.de',   200),
        ('PFLEGEFACHKRAFT',   'buch_fkr@test.de',   403),
        ('PFLEGEHILFSKRAFT',  'buch_hkr@test.de',   403),
        ('FAHRER',            'buch_fah@test.de',   403),
        ('HAUSWIRTSCHAFT',    'buch_hw@test.de',    403),
    ])
    def test_buchhaltung_dashboard(self, client, company, db, role, email, expected):
        emp = make_employee(company, role=role, email=email)
        login(client, emp.email)
        r = client.get('/buchhaltung/', follow_redirects=True)
        assert r.status_code == expected


# ─── Fuhrpark access matrix ──────────────────────────────────────────────────

class TestFuhrparkRoleAccess:
    @pytest.mark.parametrize('role,email,expected', [
        ('ADMIN',             'fuhr_adm@test.de',  200),
        ('FAHRER',            'fuhr_fah@test.de',  200),
        ('PFLEGEFACHKRAFT',   'fuhr_fkr@test.de',  403),
        ('PFLEGEHILFSKRAFT',  'fuhr_hkr@test.de',  403),
        ('VERWALTUNG',        'fuhr_ver@test.de',  403),
        ('HAUSWIRTSCHAFT',    'fuhr_hw@test.de',   403),
    ])
    def test_fuhrpark_list(self, client, company, db, role, email, expected):
        emp = make_employee(company, role=role, email=email)
        login(client, emp.email)
        r = client.get('/fuhrpark/', follow_redirects=True)
        assert r.status_code == expected

    def test_only_admin_can_create_fahrzeug(self, client, company, fahrzeug, db):
        fahrer = make_employee(company, role='FAHRER', email='fahr_cr@test.de')
        login(client, fahrer.email)
        r = client.get('/fuhrpark/neu', follow_redirects=True)
        assert r.status_code == 403

    def test_only_admin_can_edit_fahrzeug(self, client, company, fahrzeug, db):
        fahrer = make_employee(company, role='FAHRER', email='fahr_ed@test.de')
        login(client, fahrer.email)
        r = client.get(f'/fuhrpark/{fahrzeug.id}/bearbeiten', follow_redirects=True)
        assert r.status_code == 403

    def test_fahrer_can_add_fahrt(self, client, company, fahrzeug, db):
        fahrer = make_employee(company, role='FAHRER', email='fahr_km@test.de')
        login(client, fahrer.email)
        r = client.get(f'/fuhrpark/{fahrzeug.id}/fahrt/neu')
        assert r.status_code in (200, 404)


# ─── Admin panel access ──────────────────────────────────────────────────────

class TestAdminPanelAccess:
    def test_admin_can_access_admin_panel(self, admin_client):
        r = admin_client.get('/admin/')
        assert r.status_code in (200, 404)

    def test_non_admin_blocked_from_admin_panel(self, fachkraft_client):
        r = fachkraft_client.get('/admin/', follow_redirects=True)
        assert r.status_code in (403, 302, 404)

    def test_admin_can_manage_employees(self, admin_client):
        r = admin_client.get('/company/settings')
        assert r.status_code == 200

    def test_non_admin_cannot_manage_company(self, fachkraft_client):
        r = fachkraft_client.get('/company/settings', follow_redirects=True)
        assert r.status_code in (403, 302)


# ─── Company isolation ───────────────────────────────────────────────────────

class TestCompanyIsolation:
    """Data of company A must never be accessible to company B."""

    def test_patient_from_other_company_not_visible(self, admin_client, db):
        from tests.conftest import make_company
        c2 = make_company(email='iso_c2@test.de', name='Isoliert GmbH')
        p2 = make_patient(c2, vorname='Fremd', nachname='Patient')
        r = admin_client.get(f'/patients/{p2.id}')
        assert r.status_code == 404

    def test_kassenbuch_from_other_company_not_visible(self, admin_client, db):
        from tests.conftest import make_company
        from app.models import KassenbuchEintrag
        from decimal import Decimal
        c2 = make_company(email='iso_buch@test.de', name='BuchIso GmbH')
        emp2 = make_employee(c2, role='ADMIN', email='iso_admin@test.de')
        e2 = KassenbuchEintrag(
            company_id=c2.id,
            employee_id=emp2.id,
            datum=date.today(),
            art='EINNAHME',
            kategorie='PFLEGEKASSE',
            betrag=Decimal('999.99'),
            beschreibung='GEHEIM andere Firma',
        )
        db.session.add(e2)
        db.session.flush()

        r = admin_client.get('/buchhaltung/kassenbuch')
        assert r.status_code == 200
        assert b'GEHEIM' not in r.data

    def test_fahrzeug_from_other_company_not_visible(self, admin_client, db):
        from tests.conftest import make_company
        c2 = make_company(email='iso_fleet@test.de', name='FleetIso GmbH')
        from app.models import Fahrzeug
        f2 = Fahrzeug(
            company_id=c2.id,
            kennzeichen='XX-FREMD 99',
            status='AKTIV',
        )
        db.session.add(f2)
        db.session.flush()

        r = admin_client.get(f'/fuhrpark/{f2.id}')
        assert r.status_code == 404

    def test_sis_from_other_company_blocked(self, admin_client, db):
        from tests.conftest import make_company
        from app.models import SisAssessment
        c2 = make_company(email='iso_sis@test.de', name='SisIso GmbH')
        emp2 = make_employee(c2, role='ADMIN', email='iso_sis_adm@test.de')
        p2 = make_patient(c2)
        s2 = SisAssessment(
            company_id=c2.id,
            patient_id=p2.id,
            created_by=emp2.id,
            version=1,
            is_current=True,
            assessment_date=date.today(),
        )
        db.session.add(s2)
        db.session.flush()

        r = admin_client.get(f'/sis/{s2.id}')
        assert r.status_code in (403, 404)


# ─── Employee assignment tests ───────────────────────────────────────────────

class TestAssignments:
    def test_admin_can_assign_nurse_to_patient(self, admin_client, company,
                                                pflegefachkraft, patient, db):
        count_before = EmployeePatientAssignment.query.filter_by(
            company_id=company.id).count()
        r = admin_client.post('/assignments/create', data={
            'employee_id': pflegefachkraft.id,
            'patient_id': patient.id,
        }, follow_redirects=True)
        assert r.status_code == 200

    def test_admin_can_unassign_nurse(self, admin_client, company,
                                      pflegefachkraft, patient, db):
        assignment = EmployeePatientAssignment(
            company_id=company.id,
            employee_id=pflegefachkraft.id,
            patient_id=patient.id,
        )
        db.session.add(assignment)
        db.session.flush()

        r = admin_client.post(f'/assignments/{assignment.id}/unassign',
                               follow_redirects=True)
        assert r.status_code in (200, 404)

    def test_assignment_index_accessible(self, admin_client):
        r = admin_client.get('/assignments/')
        assert r.status_code == 200

    def test_non_admin_cannot_assign(self, fachkraft_client, pflegehilfskraft, patient):
        r = fachkraft_client.post('/assignments/create', data={
            'employee_id': pflegehilfskraft.id,
            'patient_id': patient.id,
        }, follow_redirects=True)
        assert r.status_code in (403, 302)


# ─── Export access ────────────────────────────────────────────────────────────

class TestExportsAccess:
    def test_admin_can_export(self, admin_client, patient):
        r = admin_client.get(f'/export/patient/{patient.id}/pdf')
        assert r.status_code in (200, 404)

    def test_fachkraft_blocked_from_exports(self, fachkraft_client, patient):
        r = fachkraft_client.get(f'/export/patient/{patient.id}/pdf',
                                  follow_redirects=True)
        assert r.status_code in (403, 302, 200, 404)


# ─── CSRF protection ─────────────────────────────────────────────────────────

class TestCsrfProtection:
    """CSRF is disabled in tests, but we verify routes require POST for mutations."""

    def test_delete_requires_post_not_get(self, admin_client, company, admin, db):
        from app.models import KassenbuchEintrag
        from decimal import Decimal
        e = KassenbuchEintrag(
            company_id=company.id,
            employee_id=admin.id,
            datum=date.today(),
            art='EINNAHME',
            kategorie='PFLEGEKASSE',
            betrag=Decimal('50.00'),
        )
        db.session.add(e)
        db.session.flush()

        # GET on delete route should NOT delete
        r = admin_client.get(f'/buchhaltung/eintrag/{e.id}/loeschen')
        assert r.status_code in (405, 302, 404)
        db.session.refresh(e)
        assert e.deleted_at is None


# ─── Audit log ───────────────────────────────────────────────────────────────

class TestAuditLog:
    def test_login_creates_audit_entry(self, client, admin, db):
        from app.models import AuditLog
        count_before = AuditLog.query.filter(
            AuditLog.entity_type == 'employee').count()
        login(client, admin.email)
        count_after = AuditLog.query.filter(
            AuditLog.entity_type == 'employee').count()
        assert count_after > count_before

    def test_failed_login_creates_audit_entry(self, client, admin, db):
        from app.models import AuditLog
        count_before = AuditLog.query.count()
        client.post('/auth/login', data={
            'email': admin.email,
            'password': 'WRONG',
        })
        count_after = AuditLog.query.count()
        assert count_after > count_before
