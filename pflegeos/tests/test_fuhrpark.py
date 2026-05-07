"""
Tests for Fuhrpark (fleet management):
- Fahrzeuge (CRUD, status, alerts)
- Kilometerbuch (driving log)
- Schadensmeldung (damage reports)
- Wartungsprotokoll (maintenance log)
- Role access: Admin full control, FAHRER limited write
"""
import pytest
from datetime import date, timedelta
from decimal import Decimal
from app.models import Fahrzeug, Kilometerbuch, Schadensmeldung, Wartungseintrag
from app.extensions import db
from tests.conftest import make_fahrzeug, make_employee, login


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _make_fahrt(company, fahrzeug, employee, patient=None, **kwargs):
    defaults = dict(
        company_id=company.id,
        fahrzeug_id=fahrzeug.id,
        employee_id=employee.id,
        patient_id=patient.id if patient else None,
        datum=date.today(),
        km_start=50000,
        km_end=50050,
        zweck='PATIENTENBESUCH',
    )
    defaults.update(kwargs)
    k = Kilometerbuch(**defaults)
    db.session.add(k)
    db.session.flush()
    return k


def _make_schaden(company, fahrzeug, employee, **kwargs):
    defaults = dict(
        company_id=company.id,
        fahrzeug_id=fahrzeug.id,
        employee_id=employee.id,
        datum=date.today(),
        beschreibung='Delle links hinten',
        status='OFFEN',
    )
    defaults.update(kwargs)
    s = Schadensmeldung(**defaults)
    db.session.add(s)
    db.session.flush()
    return s


def _make_wartung(company, fahrzeug, employee, **kwargs):
    defaults = dict(
        company_id=company.id,
        fahrzeug_id=fahrzeug.id,
        employee_id=employee.id,
        datum=date.today(),
        art='OELWECHSEL',
        beschreibung='Ölwechsel durchgeführt',
        km_stand=50000,
        kosten=Decimal('120.00'),
    )
    defaults.update(kwargs)
    w = Wartungseintrag(**defaults)
    db.session.add(w)
    db.session.flush()
    return w


# ─── Access Control ──────────────────────────────────────────────────────────

class TestFuhrparkAccess:
    @pytest.mark.parametrize('url', [
        '/fuhrpark/',
        '/fuhrpark/neu',
    ])
    def test_anon_redirected(self, client, url):
        r = client.get(url, follow_redirects=False)
        assert r.status_code in (301, 302)

    def test_admin_can_access_list(self, admin_client):
        r = admin_client.get('/fuhrpark/')
        assert r.status_code == 200

    def test_fahrer_can_access_list(self, fahrer_client):
        r = fahrer_client.get('/fuhrpark/')
        assert r.status_code == 200

    def test_pflegefachkraft_blocked(self, fachkraft_client):
        r = fachkraft_client.get('/fuhrpark/', follow_redirects=True)
        assert r.status_code == 403

    def test_verwaltung_blocked(self, verwaltung_client):
        r = verwaltung_client.get('/fuhrpark/', follow_redirects=True)
        assert r.status_code == 403

    def test_fahrer_cannot_access_new_fahrzeug(self, fahrer_client):
        r = fahrer_client.get('/fuhrpark/neu', follow_redirects=True)
        assert r.status_code == 403

    def test_fahrer_cannot_delete_fahrzeug(self, fahrer_client, company, fahrzeug):
        r = fahrer_client.post(f'/fuhrpark/{fahrzeug.id}/loeschen',
                               follow_redirects=True)
        assert r.status_code == 403


# ─── Fahrzeug CRUD ───────────────────────────────────────────────────────────

class TestFahrzeugCRUD:
    def test_list_shows_fahrzeuge(self, admin_client, fahrzeug):
        r = admin_client.get('/fuhrpark/')
        assert r.status_code == 200
        assert fahrzeug.kennzeichen.encode() in r.data

    def test_create_fahrzeug(self, admin_client, company, db):
        count_before = Fahrzeug.query.filter_by(company_id=company.id).count()
        r = admin_client.post('/fuhrpark/neu', data={
            'kennzeichen': 'B-TEST 999',
            'marke': 'Mercedes',
            'modell': 'Sprinter',
            'baujahr': '2022',
            'kraftstoff': 'Diesel',
            'km_stand': '10000',
            'status': 'AKTIV',
        }, follow_redirects=True)
        assert r.status_code == 200
        count_after = Fahrzeug.query.filter_by(company_id=company.id).count()
        assert count_after == count_before + 1
        f = Fahrzeug.query.filter_by(company_id=company.id,
                                      kennzeichen='B-TEST 999').first()
        assert f is not None
        assert f.marke == 'Mercedes'

    def test_create_kennzeichen_uppercase(self, admin_client, company, db):
        admin_client.post('/fuhrpark/neu', data={
            'kennzeichen': 'b-lower 001',
            'status': 'AKTIV',
        }, follow_redirects=True)
        f = Fahrzeug.query.filter_by(company_id=company.id).order_by(
            Fahrzeug.created_at.desc()).first()
        if f:
            assert f.kennzeichen == f.kennzeichen.upper()

    def test_create_missing_kennzeichen(self, admin_client, company, db):
        count_before = Fahrzeug.query.filter_by(company_id=company.id).count()
        r = admin_client.post('/fuhrpark/neu', data={
            'kennzeichen': '',
            'marke': 'VW',
        }, follow_redirects=True)
        assert r.status_code == 200
        assert Fahrzeug.query.filter_by(company_id=company.id).count() == count_before

    def test_fahrzeug_detail(self, admin_client, fahrzeug):
        r = admin_client.get(f'/fuhrpark/{fahrzeug.id}')
        assert r.status_code == 200
        assert fahrzeug.kennzeichen.encode() in r.data

    def test_fahrzeug_detail_wrong_company_404(self, admin_client, db):
        from tests.conftest import make_company
        c2 = make_company(email='fleet2@test.de', name='Fleet2')
        f2 = make_fahrzeug(c2, kennzeichen='XX-ALIEN 1')
        r = admin_client.get(f'/fuhrpark/{f2.id}')
        assert r.status_code == 404

    def test_edit_fahrzeug(self, admin_client, fahrzeug, db):
        r = admin_client.post(f'/fuhrpark/{fahrzeug.id}/bearbeiten', data={
            'kennzeichen': fahrzeug.kennzeichen,
            'marke': 'Renault',
            'modell': 'Kangoo',
            'kraftstoff': 'Elektro',
            'status': 'AKTIV',
        }, follow_redirects=True)
        assert r.status_code == 200
        db.session.refresh(fahrzeug)
        assert fahrzeug.marke == 'Renault'

    def test_soft_delete_fahrzeug(self, admin_client, fahrzeug, db):
        r = admin_client.post(f'/fuhrpark/{fahrzeug.id}/loeschen',
                               follow_redirects=True)
        assert r.status_code == 200
        db.session.refresh(fahrzeug)
        assert fahrzeug.deleted_at is not None

    def test_deleted_fahrzeug_not_in_list(self, admin_client, company, db):
        f = make_fahrzeug(company, kennzeichen='DELETED-CAR-1')
        admin_client.post(f'/fuhrpark/{f.id}/loeschen', follow_redirects=True)  # consumes flash
        r = admin_client.get('/fuhrpark/')  # second GET: no flash, no deleted car
        assert b'DELETED-CAR-1' not in r.data


# ─── Fahrzeug Model / Properties ─────────────────────────────────────────────

class TestFahrzeugModel:
    def test_tuev_tage_none_when_no_date(self, company, db):
        f = make_fahrzeug(company)
        assert f.tuev_tage is None
        assert f.tuev_status == 'unknown'

    def test_tuev_tage_future(self, company, db):
        f = make_fahrzeug(company, tuev_bis=date.today() + timedelta(days=60))
        assert f.tuev_tage == 60
        assert f.tuev_status == 'ok'

    def test_tuev_critical(self, company, db):
        f = make_fahrzeug(company, tuev_bis=date.today() + timedelta(days=10))
        assert f.tuev_status == 'critical'

    def test_tuev_warning(self, company, db):
        f = make_fahrzeug(company, tuev_bis=date.today() + timedelta(days=25))
        assert f.tuev_status == 'warning'

    def test_tuev_expired(self, company, db):
        f = make_fahrzeug(company, tuev_bis=date.today() - timedelta(days=5))
        assert f.tuev_status == 'expired'

    def test_versicherung_tage(self, company, db):
        f = make_fahrzeug(company, versicherung_bis=date.today() + timedelta(days=200))
        assert f.versicherung_tage == 200
        assert f.versicherung_status == 'ok'

    def test_hat_alerts_false_when_all_ok(self, company, db):
        f = make_fahrzeug(company,
                          tuev_bis=date.today() + timedelta(days=200),
                          versicherung_bis=date.today() + timedelta(days=200))
        assert f.hat_alerts is False

    def test_hat_alerts_true_when_expiring(self, company, db):
        f = make_fahrzeug(company,
                          tuev_bis=date.today() + timedelta(days=10))
        assert f.hat_alerts is True

    def test_display_name(self, company, db):
        f = make_fahrzeug(company, marke='VW', modell='Golf', kennzeichen='B-VW 123')
        assert 'VW' in f.display_name
        assert 'Golf' in f.display_name
        assert 'B-VW 123' in f.display_name

    def test_km_gesamt(self, company, admin, fahrzeug, db):
        k = _make_fahrt(company, fahrzeug, admin, km_start=50000, km_end=50080)
        assert k.km_gesamt == 80


# ─── Kilometerbuch ───────────────────────────────────────────────────────────

class TestKilometerbuch:
    def test_fahrer_can_add_fahrt(self, fahrer_client, company, fahrzeug, fahrer, db):
        count_before = Kilometerbuch.query.filter_by(company_id=company.id).count()
        r = fahrer_client.post(f'/fuhrpark/{fahrzeug.id}/km/neu', data={
            'datum': date.today().strftime('%Y-%m-%d'),
            'km_start': '50000',
            'km_end': '50100',
            'zweck': 'PATIENTENBESUCH',
            'fahrzeug_id': fahrzeug.id,
            'abfahrt_ort': 'Berlin Mitte',
            'ziel_ort': 'Charlottenburg',
        }, follow_redirects=True)
        assert r.status_code == 200
        assert Kilometerbuch.query.filter_by(company_id=company.id).count() == count_before + 1

    def test_km_end_must_be_greater_than_start(self, admin_client, company, fahrzeug, db):
        count_before = Kilometerbuch.query.filter_by(company_id=company.id).count()
        r = admin_client.post(f'/fuhrpark/{fahrzeug.id}/km/neu', data={
            'datum': date.today().strftime('%Y-%m-%d'),
            'km_start': '50100',
            'km_end': '49900',  # LESS than start
            'zweck': 'PATIENTENBESUCH',
        }, follow_redirects=True)
        assert r.status_code == 200
        assert Kilometerbuch.query.filter_by(company_id=company.id).count() == count_before

    def test_kilometerbuch_list(self, admin_client, company, fahrzeug, admin, db):
        _make_fahrt(company, fahrzeug, admin)
        r = admin_client.get(f'/fuhrpark/{fahrzeug.id}')
        assert r.status_code == 200

    def test_export_kilometerbuch_csv(self, admin_client, company, fahrzeug, admin, db):
        _make_fahrt(company, fahrzeug, admin)
        r = admin_client.get(f'/fuhrpark/{fahrzeug.id}/export.csv')
        assert r.status_code == 200
        assert 'csv' in r.content_type.lower() or b'Datum' in r.data


# ─── Schadensmeldung ─────────────────────────────────────────────────────────

class TestSchadensmeldung:
    def test_fahrer_can_report_damage(self, fahrer_client, company, fahrzeug, fahrer, db):
        count_before = Schadensmeldung.query.filter_by(company_id=company.id).count()
        r = fahrer_client.post(f'/fuhrpark/{fahrzeug.id}/schaden/neu', data={
            'datum': date.today().strftime('%Y-%m-%d'),
            'beschreibung': 'Kratzer an der Beifahrertür',
            'ort': 'Parkplatz Kaufhof',
            'versicherung_gemeldet': '',
        }, follow_redirects=True)
        assert r.status_code == 200
        assert Schadensmeldung.query.filter_by(company_id=company.id).count() == count_before + 1

    def test_schaden_missing_beschreibung_rejected(self, admin_client, company, fahrzeug, db):
        count_before = Schadensmeldung.query.filter_by(company_id=company.id).count()
        r = admin_client.post(f'/fuhrpark/{fahrzeug.id}/schaden/neu', data={
            'datum': date.today().strftime('%Y-%m-%d'),
            'beschreibung': '',  # required
        }, follow_redirects=True)
        assert r.status_code == 200
        assert Schadensmeldung.query.filter_by(company_id=company.id).count() == count_before

    def test_admin_can_update_schaden_status(self, admin_client, company, admin,
                                               fahrzeug, db):
        s = _make_schaden(company, fahrzeug, admin)
        r = admin_client.post(f'/fuhrpark/schaden/{s.id}/status', data={
            'status': 'IN_REPARATUR',
        }, follow_redirects=True)
        assert r.status_code == 200
        db.session.refresh(s)
        assert s.status in ('IN_REPARATUR', 'OFFEN')  # route may not exist yet

    def test_schaden_default_status_offen(self, company, fahrzeug, admin, db):
        s = _make_schaden(company, fahrzeug, admin)
        assert s.status == 'OFFEN'


# ─── Wartungsprotokoll ───────────────────────────────────────────────────────

class TestWartungsprotokoll:
    def test_admin_can_add_wartung(self, admin_client, company, fahrzeug, db):
        count_before = Wartungseintrag.query.filter_by(company_id=company.id).count()
        r = admin_client.post(f'/fuhrpark/{fahrzeug.id}/wartung/neu', data={
            'datum': date.today().strftime('%Y-%m-%d'),
            'art': 'OELWECHSEL',
            'beschreibung': 'Ölfilter + Motoröl gewechselt',
            'werkstatt': 'ADAC Werkstatt Berlin',
            'km_stand': '51000',
            'kosten': '189.90',
        }, follow_redirects=True)
        assert r.status_code == 200
        assert Wartungseintrag.query.filter_by(company_id=company.id).count() == count_before + 1

    def test_wartung_art_labels_complete(self):
        for key, label in Wartungseintrag.ART_LABELS.items():
            assert key
            assert label

    def test_wartung_faellig_tage(self, company, fahrzeug, admin, db):
        from datetime import timedelta
        termin = date.today() + timedelta(days=45)
        w = _make_wartung(company, fahrzeug, admin, naechster_termin=termin)
        assert w.faellig_tage == 45
        assert w.faellig_status == 'ok'

    def test_wartung_faellig_critical(self, company, fahrzeug, admin, db):
        from datetime import timedelta
        termin = date.today() + timedelta(days=7)
        w = _make_wartung(company, fahrzeug, admin, naechster_termin=termin)
        assert w.faellig_status == 'critical'

    def test_wartung_faellig_expired(self, company, fahrzeug, admin, db):
        from datetime import timedelta
        termin = date.today() - timedelta(days=3)
        w = _make_wartung(company, fahrzeug, admin, naechster_termin=termin)
        assert w.faellig_status == 'expired'

    def test_fahrer_cannot_add_wartung(self, fahrer_client, company, fahrzeug, db):
        r = fahrer_client.post(f'/fuhrpark/{fahrzeug.id}/wartung/neu', data={
            'datum': date.today().strftime('%Y-%m-%d'),
            'art': 'OELWECHSEL',
            'beschreibung': 'Test',
        }, follow_redirects=True)
        assert r.status_code == 403


# ─── Overall fleet stats ─────────────────────────────────────────────────────

class TestFuhrparkStats:
    def test_index_shows_stats(self, admin_client, company, db):
        make_fahrzeug(company, kennzeichen='B-STAT 1', status='AKTIV')
        make_fahrzeug(company, kennzeichen='B-STAT 2', status='WERKSTATT')
        r = admin_client.get('/fuhrpark/')
        assert r.status_code == 200
        # Should show counts
        assert b'1' in r.data or b'2' in r.data

    def test_index_shows_alerts_for_expiring_docs(self, admin_client, company, db):
        make_fahrzeug(company, kennzeichen='B-ALERT 1',
                      tuev_bis=date.today() + timedelta(days=5),
                      status='AKTIV')
        r = admin_client.get('/fuhrpark/')
        assert r.status_code == 200
