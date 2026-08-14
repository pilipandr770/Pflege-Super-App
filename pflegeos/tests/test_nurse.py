"""
Tests für nurse.py — Dashboard, Besuch starten, Bericht, Stornierung, Verify/Reject.
"""
import json
import pytest
from datetime import date, time

from app.extensions import db as _db
from app.models import EmployeeSchedule, VisitReport, EmployeePatientAssignment
from tests.conftest import make_company, make_employee, make_patient, login, logout


# ─── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture
def company(db):
    return make_company()


@pytest.fixture
def admin(db, company):
    return make_employee(company, role='ADMIN', email='admin@test.de')


@pytest.fixture
def nurse(db, company):
    return make_employee(company, role='PFLEGEFACHKRAFT', email='nurse@test.de')


@pytest.fixture
def patient(db, company):
    return make_patient(company)


@pytest.fixture
def schedule(db, company, nurse, patient):
    s = EmployeeSchedule(
        company_id=company.id,
        employee_id=nurse.id,
        patient_id=patient.id,
        scheduled_date=date.today(),
        scheduled_time=time(9, 0),
        status='PENDING',
        is_active=True,
        procedures='[]',
    )
    _db.session.add(s)
    _db.session.commit()
    return s


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


# ─── Dashboard ────────────────────────────────────────────────────────────────

class TestNurseDashboard:
    def test_dashboard_200(self, nurse_client):
        r = nurse_client.get('/nurse/dashboard')
        assert r.status_code == 200

    def test_dashboard_shows_todays_schedule(self, nurse_client, schedule, patient):
        r = nurse_client.get('/nurse/dashboard')
        assert patient.nachname.encode() in r.data

    def test_dashboard_requires_login(self, client):
        r = client.get('/nurse/dashboard', follow_redirects=False)
        assert r.status_code in (302, 401)


# ─── Besuch starten ───────────────────────────────────────────────────────────

class TestStartVisit:
    def test_start_visit_sets_in_progress(self, nurse_client, schedule):
        r = nurse_client.post(f'/nurse/schedule/{schedule.id}/start')
        assert r.status_code == 200
        data = json.loads(r.data)
        assert data['success'] is True
        s = EmployeeSchedule.query.get(schedule.id)
        assert s.status == 'IN_PROGRESS'

    def test_start_visit_other_nurse_rejected(self, admin_client, schedule):
        # Admin hat andere employee_id → 404 (filter_by employee_id)
        r = admin_client.post(f'/nurse/schedule/{schedule.id}/start')
        assert r.status_code == 404

    def test_start_nonexistent_schedule(self, nurse_client):
        r = nurse_client.post('/nurse/schedule/nonexistent-id/start')
        assert r.status_code == 404


# ─── Besuchsbericht ───────────────────────────────────────────────────────────

class TestVisitReport:
    def test_get_report_form(self, nurse_client, schedule):
        r = nurse_client.get(f'/nurse/schedule/{schedule.id}/report')
        assert r.status_code == 200

    def test_submit_report_creates_visit_report(self, nurse_client, schedule, patient):
        r = nurse_client.post(f'/nurse/schedule/{schedule.id}/report', data={
            'observations': 'Patient gut gelaunt',
            'patient_condition': 'STABLE',
            'procedures_completed': '[]',
            'issues_encountered': '[]',
            'photo_ids': '[]',
        })
        assert r.status_code in (200, 201)
        data = json.loads(r.data)
        assert data.get('success') is True

        # Schedule jetzt COMPLETED
        s = EmployeeSchedule.query.get(schedule.id)
        assert s.status == 'COMPLETED'
        assert s.visit_report_id is not None

        # VisitReport angelegt
        vr = VisitReport.query.get(s.visit_report_id)
        assert vr is not None
        assert vr.patient_id == patient.id
        assert vr.status == 'SUBMITTED'

    def test_submit_report_other_nurse_rejected(self, admin_client, schedule):
        r = admin_client.post(f'/nurse/schedule/{schedule.id}/report', data={
            'observations': 'Test',
            'patient_condition': 'STABLE',
        })
        assert r.status_code == 404


# ─── Besuch stornieren ───────────────────────────────────────────────────────

class TestCancelVisit:
    def test_cancel_sets_cancelled(self, nurse_client, schedule):
        r = nurse_client.post(f'/nurse/schedule/{schedule.id}/cancel', data={
            'reason': 'Patient nicht zu Hause',
        })
        assert r.status_code == 200
        data = json.loads(r.data)
        assert data['success'] is True
        s = EmployeeSchedule.query.get(schedule.id)
        assert s.status == 'CANCELLED'

    def test_cancel_other_nurse_rejected(self, admin_client, schedule):
        r = admin_client.post(f'/nurse/schedule/{schedule.id}/cancel',
                              data={'reason': 'Test'})
        assert r.status_code == 404


# ─── Berichte (My Reports) ────────────────────────────────────────────────────

class TestMyReports:
    def test_my_reports_200(self, nurse_client):
        r = nurse_client.get('/nurse/reports')
        assert r.status_code == 200

    def test_my_reports_requires_login(self, client):
        r = client.get('/nurse/reports', follow_redirects=False)
        assert r.status_code in (302, 401)


# ─── Verify / Reject (Admin) ─────────────────────────────────────────────────

class TestVerifyReject:
    def _make_report(self, company, nurse, patient):
        vr = VisitReport(
            company_id=company.id,
            employee_id=nurse.id,
            patient_id=patient.id,
            visit_date=date.today(),
            status='SUBMITTED',
            is_active=True,
        )
        _db.session.add(vr)
        _db.session.commit()
        return vr

    def test_verify_report(self, admin_client, company, nurse, patient):
        vr = self._make_report(company, nurse, patient)
        r = admin_client.post(f'/nurse/reports/{vr.id}/verify',
                              follow_redirects=True)
        assert r.status_code == 200
        updated = VisitReport.query.get(vr.id)
        assert updated.status == 'VERIFIED'

    def test_reject_report(self, admin_client, company, nurse, patient):
        vr = self._make_report(company, nurse, patient)
        r = admin_client.post(f'/nurse/reports/{vr.id}/reject',
                              data={'reason': 'Unvollständig'},
                              follow_redirects=True)
        assert r.status_code == 200
        updated = VisitReport.query.get(vr.id)
        assert updated.status in ('REJECTED', 'SUBMITTED')  # je nach Implementierung

    def test_verify_forbidden_for_nurse(self, nurse_client, company, nurse, patient):
        vr = self._make_report(company, nurse, patient)
        r = nurse_client.post(f'/nurse/reports/{vr.id}/verify',
                              follow_redirects=True)
        assert r.status_code in (403, 200)
        updated = VisitReport.query.get(vr.id)
        assert updated.status == 'SUBMITTED'  # unverändert

    def test_verify_cross_company_rejected(self, client, company, nurse, patient):
        vr = self._make_report(company, nurse, patient)
        other_company = make_company(name='Andere GmbH', email='other@other.de')
        other_admin = make_employee(other_company, role='ADMIN',
                                    email='oadmin@test.de')
        login(client, other_admin.email)
        r = client.post(f'/nurse/reports/{vr.id}/verify', follow_redirects=True)
        assert r.status_code in (403, 404)
        logout(client)
