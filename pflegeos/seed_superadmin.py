"""
seed_superadmin.py — Erstellt den globalen Superadmin-Benutzer
und Testdaten für den Fuhrpark sowie Abo-Zahlungen.

Aufruf (im Docker-Container oder lokal):
  python seed_superadmin.py
  python seed_superadmin.py --email deine@email.de --password GeheimesPasswort
"""
import sys
import argparse
from datetime import date, datetime, timedelta
from decimal import Decimal
import uuid

from app import create_app
from app.extensions import db
from app.models import (Company, Employee, Fahrzeug, Kilometerbuch,
                        SubscriptionPayment)


# ─── CLI-Argumente ────────────────────────────────────────────

parser = argparse.ArgumentParser(description='PflegeOS Superadmin Seed')
parser.add_argument('--email',    default='superadmin@pflegeos.de', help='E-Mail des Superadmins')
parser.add_argument('--password', default='SuperAdmin2024!',        help='Passwort des Superadmins')
parser.add_argument('--name',     default='Super Admin',            help='Name (Vor- und Nachname)')
args = parser.parse_args()

vorname, *rest = args.name.split(' ', 1)
nachname = rest[0] if rest else 'Admin'

# ─── App-Kontext ──────────────────────────────────────────────

app = create_app('production')

with app.app_context():

    # ── 1. Platform-Unternehmen ───────────────────────────────
    platform_company = Company.query.filter_by(slug='pflegeos-platform').first()
    if not platform_company:
        platform_company = Company(
            id=str(uuid.uuid4()),
            name='PflegeOS Platform GmbH',
            slug='pflegeos-platform',
            strasse='Musterstraße',
            hausnummer='1',
            plz='10115',
            ort='Berlin',
            bundesland='Berlin',
            email='platform@pflegeos.de',
            company_type='INTERN',
            status='ACTIVE',
            plan='PREMIUM',
        )
        db.session.add(platform_company)
        db.session.flush()
        print(f'✅ Platform-Unternehmen erstellt: {platform_company.name}')
    else:
        print(f'ℹ️  Platform-Unternehmen bereits vorhanden: {platform_company.name}')

    # ── 2. Superadmin-Benutzer ────────────────────────────────
    superadmin = Employee.query.filter_by(email=args.email).first()
    if not superadmin:
        superadmin = Employee(
            id=str(uuid.uuid4()),
            company_id=platform_company.id,
            vorname=vorname,
            nachname=nachname,
            email=args.email,
            role='ADMIN',
            is_active=True,
            is_superadmin=True,
            einstellungsdatum=date.today(),
        )
        superadmin.set_password(args.password)
        db.session.add(superadmin)
        print(f'✅ Superadmin erstellt: {args.email}')
    else:
        superadmin.is_superadmin = True
        superadmin.role = 'ADMIN'
        if args.password:
            superadmin.set_password(args.password)
        print(f'ℹ️  Superadmin aktualisiert: {args.email}')

    db.session.commit()

    # ── 3. Test-Unternehmen für Fuhrpark-Daten ────────────────
    # Erstes Nicht-Platform-Unternehmen mit mind. einem Admin
    test_company = (
        Company.query
        .filter(Company.id != platform_company.id, Company.deleted_at.is_(None))
        .order_by(Company.created_at.asc())
        .first()
    )

    if not test_company:
        print('⚠️  Kein Test-Unternehmen gefunden — Fuhrpark-Daten werden übersprungen.')
    else:
        print(f'🏢  Test-Unternehmen: {test_company.name} (ID: {test_company.id})')

        # Abo-Pläne auf TRIAL setzen falls noch TRIAL
        if test_company.plan == 'TRIAL':
            test_company.plan = 'PRO'
            test_company.status = 'ACTIVE'
            db.session.commit()
            print('   ↳ Plan auf PRO gesetzt.')

        # ── 3a. Fahrzeuge ────────────────────────────────────
        FAHRZEUGE = [
            {'kennzeichen': 'B-PF 1001', 'marke': 'VW',       'modell': 'Caddy',    'status': 'AKTIV',        'km_stand': 45000, 'kraftstoff': 'DIESEL'},
            {'kennzeichen': 'B-PF 1002', 'marke': 'Mercedes', 'modell': 'Sprinter', 'status': 'AKTIV',        'km_stand': 87000, 'kraftstoff': 'DIESEL'},
            {'kennzeichen': 'B-PF 1003', 'marke': 'Ford',     'modell': 'Transit',  'status': 'WERKSTATT',    'km_stand': 112000,'kraftstoff': 'BENZIN'},
            {'kennzeichen': 'B-PF 1004', 'marke': 'Citroën',  'modell': 'Berlingo', 'status': 'AKTIV',        'km_stand': 23000, 'kraftstoff': 'ELEKTRO'},
        ]

        fahrzeug_ids = {}
        for fdata in FAHRZEUGE:
            existing = Fahrzeug.query.filter_by(
                company_id=test_company.id,
                kennzeichen=fdata['kennzeichen'],
            ).first()
            if not existing:
                f = Fahrzeug(
                    id=str(uuid.uuid4()),
                    company_id=test_company.id,
                    kennzeichen=fdata['kennzeichen'],
                    marke=fdata['marke'],
                    modell=fdata['modell'],
                    status=fdata['status'],
                    km_stand=fdata['km_stand'],
                    kraftstoff=fdata['kraftstoff'],
                )
                db.session.add(f)
                db.session.flush()
                fahrzeug_ids[fdata['kennzeichen']] = f.id
                print(f'   🚗 Fahrzeug erstellt: {fdata["kennzeichen"]} {fdata["marke"]} {fdata["modell"]}')
            else:
                fahrzeug_ids[fdata['kennzeichen']] = existing.id
                print(f'   ℹ️  Fahrzeug vorhanden: {fdata["kennzeichen"]}')

        db.session.commit()

        # ── 3b. Kilometerbuch-Einträge ─────────────────────────
        # Ersten Fahrer/Admin der Einrichtung nehmen
        fahrer = (
            Employee.query
            .filter(
                Employee.company_id == test_company.id,
                Employee.is_active == True,
                Employee.deleted_at.is_(None),
            )
            .first()
        )

        if fahrer:
            KM_ENTRIES = [
                {'kennzeichen': 'B-PF 1001', 'datum': date.today() - timedelta(days=5),  'km_start': 44900, 'km_end': 45050, 'zweck': 'Patientenbesuche Mitte', 'abfahrt_ort': 'Berlin-Mitte', 'ziel_ort': 'Berlin-Prenzlauer Berg'},
                {'kennzeichen': 'B-PF 1001', 'datum': date.today() - timedelta(days=3),  'km_start': 45050, 'km_end': 45180, 'zweck': 'Arztfahrt Patient Müller', 'abfahrt_ort': 'Pflegeheim', 'ziel_ort': 'Charité Berlin'},
                {'kennzeichen': 'B-PF 1002', 'datum': date.today() - timedelta(days=7),  'km_start': 86800, 'km_end': 87050, 'zweck': 'Gruppenbesuch Tagespflege', 'abfahrt_ort': 'Depot', 'ziel_ort': 'Tagespflegezentrum Nord'},
                {'kennzeichen': 'B-PF 1002', 'datum': date.today() - timedelta(days=2),  'km_start': 87050, 'km_end': 87220, 'zweck': 'Materialtransport Lager', 'abfahrt_ort': 'Depot', 'ziel_ort': 'Sanitätshaus Reinickendorf'},
                {'kennzeichen': 'B-PF 1004', 'datum': date.today() - timedelta(days=1),  'km_start': 22900, 'km_end': 23050, 'zweck': 'Ambulante Pflegerunde', 'abfahrt_ort': 'Depot', 'ziel_ort': 'Mehrere Adressen Spandau'},
            ]

            for entry in KM_ENTRIES:
                kenn = entry.pop('kennzeichen')
                fz_id = fahrzeug_ids.get(kenn)
                if not fz_id:
                    continue
                exists_km = Kilometerbuch.query.filter_by(
                    fahrzeug_id=fz_id,
                    datum=entry['datum'],
                    km_start=entry['km_start'],
                ).first()
                if not exists_km:
                    km = Kilometerbuch(
                        id=str(uuid.uuid4()),
                        company_id=test_company.id,
                        fahrzeug_id=fz_id,
                        employee_id=fahrer.id,
                        **entry,
                    )
                    db.session.add(km)
                    print(f'   📍 KM-Eintrag: {kenn} {entry["datum"]}')
            db.session.commit()
        else:
            print('   ⚠️  Kein Fahrer/Mitarbeiter für KM-Einträge gefunden.')

        # ── 3c. Abo-Zahlungen (Sample) ─────────────────────────
        today = date.today()
        PAYMENTS = [
            {'plan': 'PRO', 'betrag': Decimal('149.00'), 'status': 'PAID',    'months_ago': 2, 'method': 'STRIPE'},
            {'plan': 'PRO', 'betrag': Decimal('149.00'), 'status': 'PAID',    'months_ago': 1, 'method': 'STRIPE'},
            {'plan': 'PRO', 'betrag': Decimal('149.00'), 'status': 'PENDING', 'months_ago': 0, 'method': 'STRIPE'},
        ]
        for p in PAYMENTS:
            months_ago = p.pop('months_ago')
            # Berechne Monat
            year  = today.year
            month = today.month - months_ago
            while month <= 0:
                month += 12
                year  -= 1
            period_start = date(year, month, 1)
            if month == 12:
                period_end = date(year + 1, 1, 1) - timedelta(days=1)
            else:
                period_end = date(year, month + 1, 1) - timedelta(days=1)

            exists_payment = SubscriptionPayment.query.filter_by(
                company_id=test_company.id,
                period_start=period_start,
            ).first()
            if not exists_payment:
                pmt = SubscriptionPayment(
                    id=str(uuid.uuid4()),
                    company_id=test_company.id,
                    plan=p['plan'],
                    betrag=p['betrag'],
                    period_start=period_start,
                    period_end=period_end,
                    status=p['status'],
                    payment_method=p.pop('method'),
                    paid_at=datetime(year, month, 5, 12, 0) if p['status'] == 'PAID' else None,
                )
                db.session.add(pmt)
                print(f'   💳 Zahlung: {period_start} {p["plan"]} {p["betrag"]} € [{p["status"]}]')
        db.session.commit()

    # ── Zusammenfassung ───────────────────────────────────────
    print()
    print('=' * 55)
    print('  PflegeOS Superadmin erfolgreich eingerichtet!')
    print('=' * 55)
    print(f'  URL:       http://localhost:5000/auth/login')
    print(f'  E-Mail:    {args.email}')
    print(f'  Passwort:  {args.password}')
    print(f'  Panel:     http://localhost:5000/superadmin/')
    print('=' * 55)
