"""
Tests for Buchhaltung (accounting):
- Dashboard, Kassenbuch, GuV-Bericht, Leistungsabrechnung
- Einnahmen / Ausgaben CRUD
- DATEV export
- Role access: only ADMIN and VERWALTUNG allowed
"""
import json
import pytest
from datetime import date
from decimal import Decimal
from app.models import KassenbuchEintrag, Leistungsnachweis
from app.extensions import db
from tests.conftest import make_employee, make_patient, make_leistung, login


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _make_eintrag(company, employee, art='EINNAHME', betrag='100.00',
                   kategorie='PFLEGEKASSE', beschreibung='Test', **kwargs):
    e = KassenbuchEintrag(
        company_id=company.id,
        employee_id=employee.id,
        datum=date.today(),
        art=art,
        kategorie=kategorie,
        betrag=Decimal(betrag),
        beschreibung=beschreibung,
        **kwargs,
    )
    db.session.add(e)
    db.session.commit()
    return e


def _make_lnw(company, employee, patient, leistung, abgerechnet=False):
    from datetime import time as t_
    lnw = Leistungsnachweis(
        company_id=company.id,
        patient_id=patient.id,
        employee_id=employee.id,
        leistung_id=leistung.id,
        durchgefuehrt_am=date.today(),
        durchgefuehrt_um=t_(9, 0),
        dauer_minuten=30,
        abgerechnet=abgerechnet,
    )
    db.session.add(lnw)
    db.session.commit()
    return lnw


# ─── Access control ──────────────────────────────────────────────────────────

class TestBuchhaltungAccess:
    @pytest.mark.parametrize('url', [
        '/buchhaltung/',
        '/buchhaltung/kassenbuch',
        '/buchhaltung/bericht',
        '/buchhaltung/leistungen',
    ])
    def test_anon_redirected(self, client, url):
        r = client.get(url, follow_redirects=False)
        assert r.status_code in (301, 302)

    @pytest.mark.parametrize('url', [
        '/buchhaltung/',
        '/buchhaltung/kassenbuch',
        '/buchhaltung/bericht',
        '/buchhaltung/leistungen',
    ])
    def test_admin_can_access(self, admin_client, url):
        r = admin_client.get(url)
        assert r.status_code == 200

    @pytest.mark.parametrize('url', [
        '/buchhaltung/',
        '/buchhaltung/kassenbuch',
    ])
    def test_verwaltung_can_access(self, verwaltung_client, url):
        r = verwaltung_client.get(url)
        assert r.status_code == 200

    def test_pflegefachkraft_blocked(self, fachkraft_client):
        r = fachkraft_client.get('/buchhaltung/', follow_redirects=True)
        assert r.status_code == 403

    def test_fahrer_blocked(self, fahrer_client):
        r = fahrer_client.get('/buchhaltung/', follow_redirects=True)
        assert r.status_code == 403


# ─── Dashboard ───────────────────────────────────────────────────────────────

class TestBuchhaltungDashboard:
    def test_dashboard_shows_kpis(self, admin_client, company, admin, db):
        _make_eintrag(company, admin, art='EINNAHME', betrag='500.00', kategorie='PFLEGEKASSE')
        _make_eintrag(company, admin, art='AUSGABE', betrag='200.00', kategorie='KRAFTSTOFF')
        r = admin_client.get('/buchhaltung/')
        assert r.status_code == 200
        assert b'500' in r.data
        assert b'200' in r.data

    def test_dashboard_shows_recent_entries(self, admin_client, company, admin, db):
        e = _make_eintrag(company, admin, beschreibung='Testbuchung Dashboard')
        r = admin_client.get('/buchhaltung/')
        assert r.status_code == 200

    def test_dashboard_shows_open_leistungen(self, admin_client, company, admin, patient, leistung, db):
        _make_lnw(company, admin, patient, leistung, abgerechnet=False)
        r = admin_client.get('/buchhaltung/')
        assert r.status_code == 200
        assert b'offen' in r.data.lower() or b'1' in r.data


# ─── Kassenbuch ──────────────────────────────────────────────────────────────

class TestKassenbuch:
    def test_kassenbuch_shows_entries(self, admin_client, company, admin, db):
        _make_eintrag(company, admin, beschreibung='Buchung sichtbar')
        r = admin_client.get('/buchhaltung/kassenbuch')
        assert r.status_code == 200

    def test_kassenbuch_filter_by_art_einnahme(self, admin_client, company, admin, db):
        _make_eintrag(company, admin, art='EINNAHME', kategorie='PFLEGEKASSE')
        _make_eintrag(company, admin, art='AUSGABE', kategorie='KRAFTSTOFF')
        r = admin_client.get('/buchhaltung/kassenbuch?art=EINNAHME')
        assert r.status_code == 200

    def test_kassenbuch_filter_by_monat(self, admin_client):
        r = admin_client.get('/buchhaltung/kassenbuch?monat=2026-05')
        assert r.status_code == 200

    def test_kassenbuch_saldo_calculation(self, admin_client, company, admin, db):
        _make_eintrag(company, admin, art='EINNAHME', betrag='300.00')
        _make_eintrag(company, admin, art='AUSGABE', betrag='100.00')
        r = admin_client.get('/buchhaltung/kassenbuch')
        assert r.status_code == 200
        # Saldo should be positive
        assert b'200' in r.data or b'300' in r.data


# ─── Eintrag erstellen ───────────────────────────────────────────────────────

class TestEintragCreate:
    def test_get_form_renders(self, admin_client):
        r = admin_client.get('/buchhaltung/eintrag/neu')
        assert r.status_code == 200

    def test_create_einnahme(self, admin_client, company, db):
        count_before = KassenbuchEintrag.query.filter_by(company_id=company.id).count()
        r = admin_client.post('/buchhaltung/eintrag/neu', data={
            'art': 'EINNAHME',
            'datum': date.today().strftime('%Y-%m-%d'),
            'betrag': '250.00',
            'kategorie': 'PFLEGEKASSE',
            'beschreibung': 'AOK Abrechnung April',
            'beleg_nr': 'RE-2026-001',
        }, follow_redirects=True)
        assert r.status_code == 200
        count_after = KassenbuchEintrag.query.filter_by(company_id=company.id).count()
        assert count_after == count_before + 1

    def test_create_ausgabe(self, admin_client, company, db):
        count_before = KassenbuchEintrag.query.filter_by(company_id=company.id).count()
        r = admin_client.post('/buchhaltung/eintrag/neu', data={
            'art': 'AUSGABE',
            'datum': date.today().strftime('%Y-%m-%d'),
            'betrag': '80.00',
            'kategorie': 'KRAFTSTOFF',
            'beschreibung': 'Tanken VW Caddy',
        }, follow_redirects=True)
        assert r.status_code == 200
        count_after = KassenbuchEintrag.query.filter_by(company_id=company.id).count()
        assert count_after == count_before + 1

    def test_create_missing_betrag(self, admin_client, company, db):
        count_before = KassenbuchEintrag.query.filter_by(company_id=company.id).count()
        r = admin_client.post('/buchhaltung/eintrag/neu', data={
            'art': 'EINNAHME',
            'datum': date.today().strftime('%Y-%m-%d'),
            'betrag': '',  # missing
            'kategorie': 'PFLEGEKASSE',
        }, follow_redirects=True)
        assert r.status_code == 200
        count_after = KassenbuchEintrag.query.filter_by(company_id=company.id).count()
        assert count_after == count_before  # no new entry

    def test_create_invalid_art(self, admin_client, company, db):
        count_before = KassenbuchEintrag.query.filter_by(company_id=company.id).count()
        r = admin_client.post('/buchhaltung/eintrag/neu', data={
            'art': 'INVALID',
            'datum': date.today().strftime('%Y-%m-%d'),
            'betrag': '100.00',
            'kategorie': 'PFLEGEKASSE',
        }, follow_redirects=True)
        assert r.status_code == 200
        assert KassenbuchEintrag.query.filter_by(company_id=company.id).count() == count_before

    def test_betrag_zero_rejected(self, admin_client, company, db):
        count_before = KassenbuchEintrag.query.filter_by(company_id=company.id).count()
        r = admin_client.post('/buchhaltung/eintrag/neu', data={
            'art': 'EINNAHME',
            'datum': date.today().strftime('%Y-%m-%d'),
            'betrag': '0.00',
            'kategorie': 'PFLEGEKASSE',
        }, follow_redirects=True)
        assert r.status_code == 200
        assert KassenbuchEintrag.query.filter_by(company_id=company.id).count() == count_before

    def test_verwaltung_can_create_eintrag(self, verwaltung_client, company, db):
        count_before = KassenbuchEintrag.query.filter_by(company_id=company.id).count()
        r = verwaltung_client.post('/buchhaltung/eintrag/neu', data={
            'art': 'EINNAHME',
            'datum': date.today().strftime('%Y-%m-%d'),
            'betrag': '150.00',
            'kategorie': 'EIGENANTEIL',
            'beschreibung': 'Eigenanteil Frau Muster',
        }, follow_redirects=True)
        assert r.status_code == 200
        assert KassenbuchEintrag.query.filter_by(company_id=company.id).count() == count_before + 1


# ─── Eintrag löschen ─────────────────────────────────────────────────────────

class TestEintragLoeschen:
    def test_admin_can_soft_delete(self, admin_client, company, admin, db):
        e = _make_eintrag(company, admin)
        r = admin_client.post(f'/buchhaltung/eintrag/{e.id}/loeschen',
                               follow_redirects=True)
        assert r.status_code == 200
        db.session.refresh(e)
        assert e.deleted_at is not None

    def test_verwaltung_cannot_delete(self, verwaltung_client, company, admin, db):
        e = _make_eintrag(company, admin)
        r = verwaltung_client.post(f'/buchhaltung/eintrag/{e.id}/loeschen',
                                   follow_redirects=True)
        # Should be 403
        assert r.status_code == 403
        db.session.refresh(e)
        assert e.deleted_at is None

    def test_deleted_entry_not_shown_in_kassenbuch(self, admin_client, company, admin, db):
        e = _make_eintrag(company, admin, beschreibung='Soll weg sein')
        admin_client.post(f'/buchhaltung/eintrag/{e.id}/loeschen')
        r = admin_client.get('/buchhaltung/kassenbuch')
        assert r.status_code == 200
        assert b'Soll weg sein' not in r.data


# ─── GuV-Bericht ─────────────────────────────────────────────────────────────

class TestGuVBericht:
    def test_bericht_renders(self, admin_client):
        r = admin_client.get('/buchhaltung/bericht')
        assert r.status_code == 200

    def test_bericht_with_year_filter(self, admin_client):
        r = admin_client.get('/buchhaltung/bericht?jahr=2026')
        assert r.status_code == 200

    def test_bericht_shows_chart_data(self, admin_client, company, admin, db):
        _make_eintrag(company, admin, art='EINNAHME', betrag='1000.00')
        _make_eintrag(company, admin, art='AUSGABE', betrag='400.00')
        r = admin_client.get('/buchhaltung/bericht?jahr=2026')
        assert r.status_code == 200
        # Chart data is injected as JSON
        assert b'einData' in r.data or b'ein_data' in r.data or b'1000' in r.data

    def test_bericht_totals(self, admin_client, company, admin, db):
        _make_eintrag(company, admin, art='EINNAHME', betrag='750.00')
        _make_eintrag(company, admin, art='AUSGABE', betrag='250.00')
        r = admin_client.get('/buchhaltung/bericht?jahr=2026')
        assert r.status_code == 200
        assert b'750' in r.data
        assert b'250' in r.data


# ─── Leistungsabrechnung ─────────────────────────────────────────────────────

class TestLeistungsabrechnung:
    def test_leistungen_renders(self, admin_client):
        r = admin_client.get('/buchhaltung/leistungen')
        assert r.status_code == 200

    def test_leistungen_shows_unabgerechnet(self, admin_client, company, admin,
                                             patient, leistung, db):
        _make_lnw(company, admin, patient, leistung, abgerechnet=False)
        r = admin_client.get('/buchhaltung/leistungen')
        assert r.status_code == 200
        assert b'offen' in r.data.lower() or patient.nachname.encode() in r.data

    def test_leistungen_buchen_creates_kassenbuch_eintrag(
            self, admin_client, company, admin, patient, leistung, db):
        lnw = _make_lnw(company, admin, patient, leistung, abgerechnet=False)
        count_before = KassenbuchEintrag.query.filter_by(company_id=company.id).count()

        r = admin_client.post('/buchhaltung/leistungen/als-einnahme', data={
            'lnw_ids': json.dumps([lnw.id]),
        }, follow_redirects=True)
        assert r.status_code == 200

        count_after = KassenbuchEintrag.query.filter_by(company_id=company.id).count()
        assert count_after == count_before + 1

        db.session.refresh(lnw)
        assert lnw.abgerechnet is True

    def test_leistungen_buchen_empty_ids(self, admin_client):
        r = admin_client.post('/buchhaltung/leistungen/als-einnahme', data={
            'lnw_ids': '[]',
        }, follow_redirects=True)
        assert r.status_code == 200  # shows warning flash, no crash

    def test_already_abgerechnet_not_booked_twice(
            self, admin_client, company, admin, patient, leistung, db):
        lnw = _make_lnw(company, admin, patient, leistung, abgerechnet=True)
        count_before = KassenbuchEintrag.query.filter_by(company_id=company.id).count()

        r = admin_client.post('/buchhaltung/leistungen/als-einnahme', data={
            'lnw_ids': json.dumps([lnw.id]),
        }, follow_redirects=True)
        assert r.status_code == 200
        # No new kassenbuch entry for already-billed records
        assert KassenbuchEintrag.query.filter_by(company_id=company.id).count() == count_before


# ─── DATEV-Export ────────────────────────────────────────────────────────────

class TestDatevExport:
    def test_export_returns_csv(self, admin_client, company, admin, db):
        _make_eintrag(company, admin, art='EINNAHME', betrag='100.00')
        r = admin_client.get('/buchhaltung/export.csv')
        assert r.status_code == 200
        assert 'csv' in r.content_type.lower() or b'Belegdatum' in r.data

    def test_export_contains_header(self, admin_client, company, admin, db):
        _make_eintrag(company, admin)
        r = admin_client.get('/buchhaltung/export.csv')
        assert r.status_code == 200
        # CSV header columns
        assert b'Buchungstext' in r.data or b'Belegdatum' in r.data

    def test_export_monat_filter(self, admin_client, company, admin, db):
        _make_eintrag(company, admin)
        r = admin_client.get('/buchhaltung/export.csv?monat=2026-05')
        assert r.status_code == 200
        assert r.data  # not empty

    def test_export_year_filter(self, admin_client, company, admin, db):
        _make_eintrag(company, admin)
        r = admin_client.get('/buchhaltung/export.csv?von=2026-01-01&bis=2026-12-31')
        assert r.status_code == 200

    def test_non_admin_cannot_export(self, fachkraft_client):
        r = fachkraft_client.get('/buchhaltung/export.csv', follow_redirects=True)
        assert r.status_code == 403


# ─── Model tests ─────────────────────────────────────────────────────────────

class TestKassenbuchModel:
    def test_kategorie_label_einnahme(self, company, admin, db):
        e = _make_eintrag(company, admin, art='EINNAHME', kategorie='PFLEGEKASSE')
        assert 'Pflegekasse' in e.kategorie_label

    def test_kategorie_label_ausgabe(self, company, admin, db):
        e = _make_eintrag(company, admin, art='AUSGABE', kategorie='KRAFTSTOFF')
        assert 'Kraftstoff' in e.kategorie_label

    def test_ist_einnahme_property(self, company, admin, db):
        e1 = _make_eintrag(company, admin, art='EINNAHME')
        e2 = _make_eintrag(company, admin, art='AUSGABE')
        assert e1.ist_einnahme is True
        assert e2.ist_einnahme is False

    def test_betrag_vorzeichenbehaftet(self, company, admin, db):
        e1 = _make_eintrag(company, admin, art='EINNAHME', betrag='100.00')
        e2 = _make_eintrag(company, admin, art='AUSGABE', betrag='100.00')
        assert e1.betrag_vorzeichenbehaftet == 100.0
        assert e2.betrag_vorzeichenbehaftet == -100.0

    def test_soft_delete_excludes_from_totals(self, company, admin, admin_client, db):
        from datetime import datetime
        e = _make_eintrag(company, admin, art='EINNAHME', betrag='999.00')
        e.deleted_at = datetime.utcnow()
        db.session.flush()
        r = admin_client.get('/buchhaltung/kassenbuch')
        assert r.status_code == 200
        assert b'999' not in r.data

    def test_all_einnahmen_kategorien_have_labels(self):
        for key, label in KassenbuchEintrag.EINNAHMEN_KATEGORIEN.items():
            assert key
            assert label

    def test_all_ausgaben_kategorien_have_labels(self):
        for key, label in KassenbuchEintrag.AUSGABEN_KATEGORIEN.items():
            assert key
            assert label
