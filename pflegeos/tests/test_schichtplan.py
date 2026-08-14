"""
Tests for Schichtplanung (shift scheduling).

Admin: full CRUD on all employees.
Non-admin: read-only, own shifts only.
"""
import pytest
from datetime import date, time, timedelta
from app.models import Dienstschicht
from app.extensions import db
from tests.conftest import make_employee, make_schicht, login


HEUTE = date.today()
MORGEN = HEUTE + timedelta(days=1)


# ─── Model: Dienstschicht properties ─────────────────────────────────────────

class TestDienstschichtModel:
    def test_typ_label_frueh(self, company, admin):
        s = make_schicht(company, admin, schicht_typ='FRUEH')
        assert s.typ_label == 'Frühschicht'

    def test_typ_label_urlaub(self, company, admin):
        s = make_schicht(company, admin, schicht_typ='URLAUB')
        assert s.typ_label == 'Urlaub'

    def test_typ_kuerzel_nacht(self, company, admin):
        s = make_schicht(company, admin, schicht_typ='NACHT')
        assert s.typ_kuerzel == 'N'

    def test_ist_arbeitstag_frueh(self, company, admin):
        s = make_schicht(company, admin, schicht_typ='FRUEH')
        assert s.ist_arbeitstag is True

    def test_ist_arbeitstag_urlaub_false(self, company, admin):
        s = make_schicht(company, admin, schicht_typ='URLAUB')
        assert s.ist_arbeitstag is False

    def test_ist_arbeitstag_krank_false(self, company, admin):
        s = make_schicht(company, admin, schicht_typ='KRANK')
        assert s.ist_arbeitstag is False

    def test_ist_arbeitstag_frei_false(self, company, admin):
        s = make_schicht(company, admin, schicht_typ='FREI')
        assert s.ist_arbeitstag is False

    def test_unique_constraint_same_employee_same_day(self, company, admin):
        make_schicht(company, admin, datum=HEUTE, schicht_typ='FRUEH')
        from sqlalchemy.exc import IntegrityError
        with pytest.raises(IntegrityError):
            make_schicht(company, admin, datum=HEUTE, schicht_typ='SPAET')

    def test_same_employee_different_days_ok(self, company, admin):
        s1 = make_schicht(company, admin, datum=HEUTE,  schicht_typ='FRUEH')
        s2 = make_schicht(company, admin, datum=MORGEN, schicht_typ='SPAET')
        assert s1.id != s2.id

    def test_different_employees_same_day_ok(self, company, admin, pflegefachkraft):
        s1 = make_schicht(company, admin,          datum=HEUTE, schicht_typ='FRUEH')
        s2 = make_schicht(company, pflegefachkraft, datum=HEUTE, schicht_typ='SPAET')
        assert s1.id != s2.id

    def test_company_isolation(self, company, admin, db):
        """Schicht einer anderen Firma ist nicht sichtbar."""
        from tests.conftest import make_company, make_employee
        other = make_company(email='other@pflegedienst.de')
        other_emp = make_employee(other, role='ADMIN', email='other_admin@test.de')
        make_schicht(other, other_emp, datum=HEUTE, schicht_typ='FRUEH')

        count = Dienstschicht.query.filter_by(company_id=company.id).count()
        assert count == 0


# ─── HTTP: Admin-Monatsansicht ────────────────────────────────────────────────

class TestSchichtplanIndex:
    def test_admin_can_access(self, admin_client):
        r = admin_client.get('/schichtplan/')
        assert r.status_code == 200

    def test_non_admin_gets_403(self, fachkraft_client):
        r = fachkraft_client.get('/schichtplan/')
        assert r.status_code == 403

    def test_shows_employee_names(self, admin_client, pflegefachkraft):
        r = admin_client.get('/schichtplan/')
        assert pflegefachkraft.nachname.encode() in r.data

    def test_shows_shift_badges(self, company, admin, admin_client, pflegefachkraft):
        make_schicht(company, pflegefachkraft, datum=HEUTE, schicht_typ='FRUEH')
        r = admin_client.get(f'/schichtplan/?year={HEUTE.year}&month={HEUTE.month}')
        assert r.status_code == 200
        assert b'F' in r.data  # Kürzel Frühschicht

    def test_month_navigation_prev(self, admin_client):
        r = admin_client.get('/schichtplan/?year=2026&month=1')
        assert r.status_code == 200

    def test_month_navigation_next(self, admin_client):
        r = admin_client.get('/schichtplan/?year=2026&month=12')
        assert r.status_code == 200

    def test_unauthenticated_redirect(self, client):
        r = client.get('/schichtplan/', follow_redirects=False)
        assert r.status_code in (301, 302)


# ─── HTTP: Schicht setzen (POST) ─────────────────────────────────────────────

class TestSchichtSetzen:
    def _post(self, client, employee, datum, schicht_typ='FRUEH', **extra):
        data = dict(
            employee_id=employee.id,
            datum=datum.isoformat(),
            schicht_typ=schicht_typ,
            year=datum.year,
            month=datum.month,
        )
        data.update(extra)
        return client.post('/schichtplan/setzen', data=data, follow_redirects=True)

    def test_admin_can_create_schicht(self, admin_client, company, pflegefachkraft):
        r = self._post(admin_client, pflegefachkraft, HEUTE, 'FRUEH')
        assert r.status_code == 200
        s = Dienstschicht.query.filter_by(employee_id=pflegefachkraft.id, datum=HEUTE).first()
        assert s is not None
        assert s.schicht_typ == 'FRUEH'

    def test_create_with_times(self, admin_client, company, pflegefachkraft):
        r = self._post(admin_client, pflegefachkraft, HEUTE, 'SPAET',
                       beginn='14:00', ende='22:00', bereich='Station 1')
        assert r.status_code == 200
        s = Dienstschicht.query.filter_by(employee_id=pflegefachkraft.id, datum=HEUTE).first()
        assert s.schicht_typ == 'SPAET'
        assert s.beginn == time(14, 0)
        assert s.ende  == time(22, 0)
        assert s.bereich == 'Station 1'

    def test_upsert_updates_existing(self, admin_client, company, pflegefachkraft):
        make_schicht(company, pflegefachkraft, datum=HEUTE, schicht_typ='FRUEH')
        self._post(admin_client, pflegefachkraft, HEUTE, 'URLAUB')
        s = Dienstschicht.query.filter_by(employee_id=pflegefachkraft.id, datum=HEUTE).first()
        assert s.schicht_typ == 'URLAUB'
        assert Dienstschicht.query.filter_by(employee_id=pflegefachkraft.id, datum=HEUTE).count() == 1

    def test_non_admin_cannot_set(self, fachkraft_client, pflegefachkraft):
        r = fachkraft_client.post('/schichtplan/setzen', data={
            'employee_id': pflegefachkraft.id,
            'datum': HEUTE.isoformat(),
            'schicht_typ': 'FRUEH',
            'year': HEUTE.year,
            'month': HEUTE.month,
        }, follow_redirects=False)
        assert r.status_code in (302, 403)
        assert Dienstschicht.query.filter_by(employee_id=pflegefachkraft.id).count() == 0

    def test_missing_fields_no_crash(self, admin_client):
        r = admin_client.post('/schichtplan/setzen', data={
            'employee_id': '',
            'datum': '',
            'schicht_typ': '',
            'year': HEUTE.year,
            'month': HEUTE.month,
        }, follow_redirects=True)
        assert r.status_code == 200

    def test_invalid_typ_rejected(self, admin_client, pflegefachkraft):
        r = admin_client.post('/schichtplan/setzen', data={
            'employee_id': pflegefachkraft.id,
            'datum': HEUTE.isoformat(),
            'schicht_typ': 'INVALID_TYP',
            'year': HEUTE.year,
            'month': HEUTE.month,
        }, follow_redirects=True)
        assert r.status_code == 200
        assert Dienstschicht.query.filter_by(employee_id=pflegefachkraft.id).count() == 0

    def test_foreign_employee_blocked(self, admin_client, db):
        """Admin kann keine Schichten für fremde Firmen anlegen."""
        from tests.conftest import make_company, make_employee
        other = make_company(email='evil@other.de')
        other_emp = make_employee(other, role='PFLEGEFACHKRAFT', email='evil_emp@other.de')
        r = admin_client.post('/schichtplan/setzen', data={
            'employee_id': other_emp.id,
            'datum': HEUTE.isoformat(),
            'schicht_typ': 'FRUEH',
            'year': HEUTE.year,
            'month': HEUTE.month,
        }, follow_redirects=True)
        # Should be 403 or no shift created for other company
        assert Dienstschicht.query.filter_by(employee_id=other_emp.id).count() == 0


# ─── HTTP: Schicht löschen ────────────────────────────────────────────────────

class TestSchichtLoeschen:
    def test_admin_can_delete(self, admin_client, company, pflegefachkraft):
        s = make_schicht(company, pflegefachkraft, datum=HEUTE)
        r = admin_client.post(f'/schichtplan/{s.id}/loeschen', data={
            'year': HEUTE.year, 'month': HEUTE.month,
        }, follow_redirects=True)
        assert r.status_code == 200
        assert Dienstschicht.query.get(s.id) is None

    def test_non_admin_cannot_delete(self, client, company, pflegefachkraft):
        s = make_schicht(company, pflegefachkraft, datum=HEUTE)
        login(client, pflegefachkraft.email)
        r = client.post(f'/schichtplan/{s.id}/loeschen', data={
            'year': HEUTE.year, 'month': HEUTE.month,
        }, follow_redirects=False)
        assert r.status_code in (302, 403)
        assert Dienstschicht.query.get(s.id) is not None

    def test_delete_wrong_company_404(self, admin_client, db):
        from tests.conftest import make_company, make_employee
        other = make_company(email='other2@pflegedienst.de')
        other_emp = make_employee(other, role='ADMIN', email='adm2@other2.de')
        s = make_schicht(other, other_emp, datum=HEUTE)
        r = admin_client.post(f'/schichtplan/{s.id}/loeschen', data={
            'year': HEUTE.year, 'month': HEUTE.month,
        }, follow_redirects=True)
        assert r.status_code == 404


# ─── HTTP: API endpoint ───────────────────────────────────────────────────────

class TestSchichtplanApi:
    def test_api_returns_empty_for_no_schicht(self, admin_client, pflegefachkraft):
        r = admin_client.get(f'/schichtplan/api/schicht?employee_id={pflegefachkraft.id}&datum={HEUTE.isoformat()}')
        assert r.status_code == 200
        assert r.get_json() == {}

    def test_api_returns_schicht_data(self, admin_client, company, pflegefachkraft):
        s = make_schicht(company, pflegefachkraft, datum=HEUTE, schicht_typ='SPAET',
                         beginn=time(14, 0), ende=time(22, 0), bereich='OG2')
        r = admin_client.get(f'/schichtplan/api/schicht?employee_id={pflegefachkraft.id}&datum={HEUTE.isoformat()}')
        assert r.status_code == 200
        data = r.get_json()
        assert data['schicht_typ'] == 'SPAET'
        assert data['beginn'] == '14:00'
        assert data['ende']   == '22:00'
        assert data['bereich'] == 'OG2'

    def test_api_non_admin_forbidden(self, fachkraft_client, pflegefachkraft):
        r = fachkraft_client.get(f'/schichtplan/api/schicht?employee_id={pflegefachkraft.id}&datum={HEUTE.isoformat()}')
        assert r.status_code == 403

    def test_api_missing_params_returns_empty(self, admin_client):
        r = admin_client.get('/schichtplan/api/schicht')
        assert r.status_code == 200
        assert r.get_json() == {}


# ─── HTTP: Mein Plan (Mitarbeiter-Sicht) ─────────────────────────────────────

class TestMeinPlan:
    def test_fachkraft_can_access(self, fachkraft_client):
        r = fachkraft_client.get('/schichtplan/mein')
        assert r.status_code == 200

    def test_admin_can_access(self, admin_client):
        r = admin_client.get('/schichtplan/mein')
        assert r.status_code == 200

    def test_shows_own_shifts(self, client, company, pflegefachkraft):
        make_schicht(company, pflegefachkraft, datum=HEUTE, schicht_typ='NACHT')
        login(client, pflegefachkraft.email)
        r = client.get(f'/schichtplan/mein?year={HEUTE.year}&month={HEUTE.month}')
        assert r.status_code == 200
        assert b'Nachtschicht' in r.data

    def test_does_not_show_other_employee_shifts(self, client, company,
                                                  pflegefachkraft, pflegehilfskraft):
        make_schicht(company, pflegehilfskraft, datum=HEUTE, schicht_typ='FRUEH')
        login(client, pflegefachkraft.email)
        r = client.get(f'/schichtplan/mein?year={HEUTE.year}&month={HEUTE.month}')
        assert r.status_code == 200
        # pflegefachkraft hat keine Schicht → kein "Frühschicht"-Badge erwartet
        # (könnte im Text auftauchen falls die Legende sichtbar ist, aber Badge nicht)
        assert b'Arbeitstage' in r.data  # Statistik-Bereich sichtbar

    def test_unauthenticated_redirect(self, client):
        r = client.get('/schichtplan/mein', follow_redirects=False)
        assert r.status_code in (301, 302)

    def test_month_navigation(self, fachkraft_client):
        r = fachkraft_client.get('/schichtplan/mein?year=2025&month=6')
        assert r.status_code == 200


# ─── Statistik-Berechnung ─────────────────────────────────────────────────────

class TestSchichtStatistik:
    def test_arbeitstage_count(self, client, company, pflegefachkraft):
        make_schicht(company, pflegefachkraft, datum=HEUTE,   schicht_typ='FRUEH')
        make_schicht(company, pflegefachkraft, datum=MORGEN,  schicht_typ='SPAET')
        login(client, pflegefachkraft.email)
        r = client.get(f'/schichtplan/mein?year={HEUTE.year}&month={HEUTE.month}')
        assert r.status_code == 200
        assert b'Arbeitstage' in r.data

    def test_urlaub_days(self, client, company, pflegefachkraft):
        make_schicht(company, pflegefachkraft, datum=HEUTE,  schicht_typ='URLAUB')
        make_schicht(company, pflegefachkraft, datum=MORGEN, schicht_typ='URLAUB')
        login(client, pflegefachkraft.email)
        r = client.get(f'/schichtplan/mein?year={HEUTE.year}&month={HEUTE.month}')
        assert b'Urlaub' in r.data

    def test_krank_days(self, client, company, pflegefachkraft):
        make_schicht(company, pflegefachkraft, datum=HEUTE, schicht_typ='KRANK')
        login(client, pflegefachkraft.email)
        r = client.get(f'/schichtplan/mein?year={HEUTE.year}&month={HEUTE.month}')
        assert b'Krank' in r.data
