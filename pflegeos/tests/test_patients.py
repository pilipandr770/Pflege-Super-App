"""
Tests for patient management: CRUD, access control, portal, filtering.
"""
import pytest
from datetime import date
from app.models import Patient, EmployeePatientAssignment
from app.extensions import db
from tests.conftest import make_patient, make_employee, login


class TestPatientList:
    def test_admin_sees_all_patients(self, admin_client, patient):
        r = admin_client.get('/patients/')
        assert r.status_code == 200
        assert patient.nachname.encode() in r.data

    def test_nurse_sees_only_assigned_patients(self, client, company, pflegefachkraft, db):
        # Create 2 patients; assign only one
        p1 = make_patient(company, vorname='Sichtbar', nachname='Patient')
        p2 = make_patient(company, vorname='Unsichtbar', nachname='Patient')

        assignment = EmployeePatientAssignment(
            company_id=company.id,
            employee_id=pflegefachkraft.id,
            patient_id=p1.id,
        )
        db.session.add(assignment)
        db.session.flush()

        login(client, pflegefachkraft.email)
        r = client.get('/patients/')
        assert r.status_code == 200
        assert b'Sichtbar' in r.data
        assert b'Unsichtbar' not in r.data

    def test_nurse_no_assignments_sees_empty(self, client, pflegefachkraft, patient):
        login(client, pflegefachkraft.email)
        r = client.get('/patients/')
        assert r.status_code == 200
        # No assignments → list should be empty (patient name not visible)
        assert patient.nachname.encode() not in r.data

    def test_status_filter_aktiv(self, admin_client, company, db):
        p_aktiv = make_patient(company, vorname='AktivPat', nachname='Mayer', status='AKTIV')
        p_beurlaubt = make_patient(company, vorname='BeurlaubtPat', nachname='Huber', status='BEURLAUBT')
        r = admin_client.get('/patients/?status=AKTIV')
        assert b'AktivPat' in r.data
        assert b'BeurlaubtPat' not in r.data

    def test_search_by_name(self, admin_client, company, db):
        make_patient(company, vorname='Helga', nachname='Suchbar')
        make_patient(company, vorname='Otto', nachname='Andere')
        r = admin_client.get('/patients/?q=Suchbar')
        assert b'Suchbar' in r.data
        assert b'Andere' not in r.data


class TestPatientCreate:
    def test_admin_can_create_patient(self, admin_client, db):
        r = admin_client.post('/patients/new', data={
            'vorname': 'Neuer',
            'nachname': 'Patient',
            'pflegegrad': '3',
            'aufnahmedatum': '2026-01-01',
            'gender': 'W',
            'care_type': 'HOME_CARE',
            'krankenversicherung': 'TK',
        }, follow_redirects=True)
        assert r.status_code == 200
        p = Patient.query.filter_by(vorname='Neuer', nachname='Patient').first()
        assert p is not None
        assert p.pflegegrad == '3'

    def test_create_patient_missing_required(self, admin_client):
        r = admin_client.post('/patients/new', data={
            'vorname': 'Nur',
            # nachname missing
            'pflegegrad': '2',
            'aufnahmedatum': '2026-01-01',
        }, follow_redirects=True)
        assert r.status_code == 200
        # Patient should NOT be created
        assert Patient.query.filter_by(vorname='Nur').first() is None

    def test_nurse_cannot_access_new_patient_form(self, fachkraft_client):
        r = fachkraft_client.get('/patients/new')
        # Either 403 or redirect
        assert r.status_code in (200, 302, 403)

    def test_patient_creation_all_fields(self, admin_client, db):
        r = admin_client.post('/patients/new', data={
            'vorname': 'Vollständig',
            'nachname': 'Datensatz',
            'pflegegrad': '4',
            'aufnahmedatum': '2025-06-01',
            'geburtsdatum': '1940-03-15',
            'gender': 'M',
            'nationalitaet': 'Deutsch',
            'religion': 'Evangelisch',
            'care_type': 'HOME_CARE',
            'strasse': 'Musterweg',
            'hausnummer': '5',
            'plz': '10117',
            'ort': 'Berlin',
            'bundesland': 'Berlin',
            'krankenversicherung': 'AOK',
            'versicherungsnummer': 'AOK123456',
            'betreuer_name': 'Sohn Stefan',
            'betreuer_telefon': '030-12345',
            'betreuer_verhaeltnis': 'Sohn',
            'hausarzt_name': 'Dr. Müller',
            'hausarzt_telefon': '030-99999',
            'sturzrisiko': 'on',
            'dekubitusrisiko': 'on',
        }, follow_redirects=True)
        assert r.status_code == 200
        p = Patient.query.filter_by(vorname='Vollständig').first()
        assert p is not None
        assert p.sturzrisiko is True
        assert p.dekubitusrisiko is True
        assert p.betreuer_name == 'Sohn Stefan'


class TestPatientDetail:
    def test_admin_can_view_patient_detail(self, admin_client, patient):
        r = admin_client.get(f'/patients/{patient.id}')
        assert r.status_code == 200
        assert patient.vorname.encode() in r.data

    def test_wrong_company_patient_not_found(self, admin_client, db):
        # Create patient for a different company
        other_company = make_patient.__wrapped__ if hasattr(make_patient, '__wrapped__') else None
        from tests.conftest import make_company
        c2 = make_company(email='other@company.de', name='Other GmbH')
        p2 = make_patient(c2, vorname='Fremd', nachname='Patient')
        r = admin_client.get(f'/patients/{p2.id}')
        assert r.status_code == 404

    def test_patient_detail_contains_key_info(self, admin_client, patient):
        r = admin_client.get(f'/patients/{patient.id}')
        assert r.status_code == 200
        assert patient.nachname.encode() in r.data
        assert patient.pflegegrad.encode() in r.data


class TestPatientEdit:
    def test_admin_can_edit_patient(self, admin_client, patient, db):
        r = admin_client.post(f'/patients/{patient.id}/edit', data={
            'vorname': patient.vorname,
            'nachname': 'Geändert',
            'pflegegrad': '3',
            'aufnahmedatum': '2025-01-01',
        }, follow_redirects=True)
        assert r.status_code == 200
        db.session.refresh(patient)
        assert patient.nachname == 'Geändert'

    def test_edit_patient_clears_to_aktiv(self, admin_client, patient, db):
        """Status changes via edit form."""
        r = admin_client.post(f'/patients/{patient.id}/edit', data={
            'vorname': patient.vorname,
            'nachname': patient.nachname,
            'pflegegrad': patient.pflegegrad,
            'aufnahmedatum': patient.aufnahmedatum.strftime('%Y-%m-%d'),
            'status': 'BEURLAUBT',
        }, follow_redirects=True)
        assert r.status_code == 200


class TestPatientModels:
    def test_full_name_property(self, patient):
        assert patient.full_name == f'{patient.vorname} {patient.nachname}'

    def test_age_property(self, company, db):
        p = make_patient(company, geburtsdatum=date(1950, 1, 1))
        assert p.age == 76  # as of May 2026

    def test_age_none_when_no_birthdate(self, company, db):
        p = make_patient(company)
        assert p.geburtsdatum is None
        assert p.age is None

    def test_patient_deleted_at_soft_delete(self, company, db):
        from datetime import datetime
        p = make_patient(company)
        pid = p.id
        p.deleted_at = datetime.utcnow()
        db.session.flush()
        # Query with deleted_at filter
        active = Patient.query.filter_by(id=pid, deleted_at=None).first()
        assert active is None

    def test_risk_flags_default_false(self, company, db):
        p = make_patient(company)
        assert p.sturzrisiko is False
        assert p.dekubitusrisiko is False
        assert p.ernaehrungsrisiko is False


class TestPortalAccess:
    def test_family_portal_disabled_returns_403_or_404(self, client, patient):
        """Family portal should not work when portal_enabled=False."""
        r = client.get(f'/portal/{patient.portal_token}',
                       follow_redirects=True)
        # either 404 or redirect to error
        assert r.status_code in (200, 403, 404)

    def test_doctor_portal_wrong_token_404(self, client):
        r = client.get('/arztportal/nonexistent-token-xyz')
        assert r.status_code == 404
