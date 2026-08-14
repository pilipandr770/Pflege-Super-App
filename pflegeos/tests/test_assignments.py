"""
Tests für assignments.py — Zuweisungen erstellen, entfernen, API.
"""
import pytest
import json
from app.extensions import db as _db
from app.models import EmployeePatientAssignment
from tests.conftest import make_company, make_employee, make_patient, login, logout


@pytest.fixture
def company(db):
    return make_company()


@pytest.fixture
def admin(db, company):
    return make_employee(company, role='ADMIN',
                         email='admin@test.de')


@pytest.fixture
def nurse(db, company):
    return make_employee(company, role='PFLEGEFACHKRAFT',
                         email='nurse@test.de')


@pytest.fixture
def patient(db, company):
    return make_patient(company)


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


# ─── Index-Seite ─────────────────────────────────────────────────────────────

class TestAssignmentsIndex:
    def test_index_200_for_admin(self, admin_client):
        r = admin_client.get('/assignments/')
        assert r.status_code == 200

    def test_index_403_for_nurse(self, nurse_client):
        r = nurse_client.get('/assignments/')
        assert r.status_code in (403, 302)


# ─── Zuweisung erstellen ──────────────────────────────────────────────────────

class TestAssignmentsCreate:
    def test_create_assignment(self, admin_client, nurse, patient, company):
        r = admin_client.post('/assignments/create', data={
            'employee_id': nurse.id,
            'patient_id': patient.id,
            'role': 'PRIMARY_NURSE',
        }, follow_redirects=True)
        assert r.status_code == 200
        a = EmployeePatientAssignment.query.filter_by(
            employee_id=nurse.id, patient_id=patient.id, is_active=True
        ).first()
        assert a is not None
        assert a.company_id == company.id

    def test_duplicate_assignment_not_created(self, admin_client, nurse, patient, company):
        # Erstes Mal anlegen
        admin_client.post('/assignments/create', data={
            'employee_id': nurse.id,
            'patient_id': patient.id,
            'role': 'PRIMARY_NURSE',
        }, follow_redirects=True)
        # Zweites Mal → kein Duplikat
        admin_client.post('/assignments/create', data={
            'employee_id': nurse.id,
            'patient_id': patient.id,
            'role': 'PRIMARY_NURSE',
        }, follow_redirects=True)
        count = EmployeePatientAssignment.query.filter_by(
            employee_id=nurse.id, patient_id=patient.id, is_active=True
        ).count()
        assert count == 1

    def test_create_missing_fields_rejected(self, admin_client, nurse):
        r = admin_client.post('/assignments/create', data={
            'employee_id': nurse.id,
            'patient_id': '',
        }, follow_redirects=True)
        assert r.status_code == 200
        assert EmployeePatientAssignment.query.count() == 0

    def test_create_cross_company_rejected(self, admin_client, admin, company):
        other_company = make_company(name='Andere GmbH', email='other@other.de')
        foreign_nurse = make_employee(other_company, role='PFLEGEFACHKRAFT',
                                      email='fremde@test.de')
        foreign_patient = make_patient(other_company, nachname='Fremd')
        r = admin_client.post('/assignments/create', data={
            'employee_id': foreign_nurse.id,
            'patient_id': foreign_patient.id,
            'role': 'PRIMARY_NURSE',
        }, follow_redirects=True)
        assert r.status_code == 200
        assert EmployeePatientAssignment.query.count() == 0

    def test_create_forbidden_for_nurse(self, nurse_client, nurse, patient):
        r = nurse_client.post('/assignments/create', data={
            'employee_id': nurse.id,
            'patient_id': patient.id,
        }, follow_redirects=True)
        assert r.status_code in (403, 200)
        assert EmployeePatientAssignment.query.count() == 0


# ─── Zuweisung entfernen ──────────────────────────────────────────────────────

class TestAssignmentsRemove:
    def _make_assignment(self, company, nurse, patient):
        a = EmployeePatientAssignment(
            company_id=company.id,
            employee_id=nurse.id,
            patient_id=patient.id,
            role='PRIMARY_NURSE',
            is_active=True,
        )
        _db.session.add(a)
        _db.session.commit()
        return a

    def test_remove_assignment(self, admin_client, nurse, patient, company):
        a = self._make_assignment(company, nurse, patient)
        r = admin_client.post(f'/assignments/{a.id}/remove',
                              follow_redirects=True)
        assert r.status_code == 200
        updated = EmployeePatientAssignment.query.get(a.id)
        assert updated is None or updated.is_active is False

    def test_remove_cross_company_rejected(self, admin_client, company):
        other_company = make_company(name='Andere GmbH', email='other2@other.de')
        foreign_nurse = make_employee(other_company, role='PFLEGEFACHKRAFT',
                                      email='fn2@test.de')
        foreign_patient = make_patient(other_company, nachname='Fremd2')
        a = EmployeePatientAssignment(
            company_id=other_company.id,
            employee_id=foreign_nurse.id,
            patient_id=foreign_patient.id,
            role='PRIMARY_NURSE',
            is_active=True,
        )
        _db.session.add(a)
        _db.session.commit()
        r = admin_client.post(f'/assignments/{a.id}/remove',
                              follow_redirects=True)
        assert r.status_code in (403, 404)
        assert EmployeePatientAssignment.query.get(a.id).is_active is True

    def test_remove_forbidden_for_nurse(self, nurse_client, nurse, patient, company):
        a = self._make_assignment(company, nurse, patient)
        r = nurse_client.post(f'/assignments/{a.id}/remove',
                              follow_redirects=True)
        assert r.status_code in (403, 200)
        assert EmployeePatientAssignment.query.get(a.id).is_active is True


# ─── API-Endpunkte ────────────────────────────────────────────────────────────

class TestAssignmentsApi:
    def test_api_employee_patients(self, admin_client, nurse, patient, company):
        a = EmployeePatientAssignment(
            company_id=company.id,
            employee_id=nurse.id,
            patient_id=patient.id,
            role='PRIMARY_NURSE',
            is_active=True,
        )
        _db.session.add(a)
        _db.session.commit()

        r = admin_client.get(f'/assignments/api/employee/{nurse.id}/patients')
        assert r.status_code == 200
        data = json.loads(r.data)
        assert isinstance(data, list)
        ids = [p['id'] for p in data]
        assert patient.id in ids

    def test_api_patient_nurses(self, admin_client, nurse, patient, company):
        a = EmployeePatientAssignment(
            company_id=company.id,
            employee_id=nurse.id,
            patient_id=patient.id,
            role='PRIMARY_NURSE',
            is_active=True,
        )
        _db.session.add(a)
        _db.session.commit()

        r = admin_client.get(f'/assignments/api/patient/{patient.id}/nurses')
        assert r.status_code == 200
        data = json.loads(r.data)
        assert isinstance(data, list)
        ids = [e['id'] for e in data]
        assert nurse.id in ids

    def test_api_cross_company_returns_empty(self, admin_client, company):
        other_company = make_company(name='Andere GmbH', email='other3@other.de')
        foreign_nurse = make_employee(other_company, role='PFLEGEFACHKRAFT',
                                      email='fn3@test.de')
        r = admin_client.get(f'/assignments/api/employee/{foreign_nurse.id}/patients')
        assert r.status_code == 200
        data = json.loads(r.data)
        assert data == []
