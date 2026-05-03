#!/usr/bin/env python
"""End-to-end workflow testing for PflegeOS features."""

import os
from datetime import datetime, date, timedelta
from app import create_app
from app.extensions import db
from app.models import (
    Company, Employee, Patient, MedicationPlan, Medication,
    SisAssessment, MedicationAdministration, BtmBuch, Leistungskatalog
)

def setup_test_data():
    """Create test company, employees, and patients."""
    print("\n" + "="*70)
    print("SETUP: Creating test data")
    print("="*70)

    # Create test company if it doesn't exist
    company = Company.query.filter_by(name='Test Facility').first()
    if company:
        print("[INFO] Test company already exists, using existing data")
        employees = Employee.query.filter_by(company_id=company.id).all()
        patients = Patient.query.filter_by(company_id=company.id).all()
    else:
        company = Company(
            name='Test Facility',
            name_zusatz='Demo Pflegeheim',
            company_type='STATIONAER',
            plaetze_anzahl=20,
            strasse='Teststrasse',
            hausnummer='1',
            plz='12345',
            ort='Teststadt',
            bundesland='Berlin',
            email='admin@testfacility.local',
            geschaeftsfuehrer_name='Max Mustermann',
            pdl_name='Dr. Weber'
        )
        db.session.add(company)
        db.session.commit()
        print(f"[OK] Created test company: {company.name}")

        # Create test employees
        employees_data = [
            {
                'vorname': 'Anna',
                'nachname': 'Mueller',
                'email': 'anna.mueller@testfacility.local',
                'role': 'ADMIN',
                'is_active': True,
                'can_administer_btm': True
            },
            {
                'vorname': 'Klaus',
                'nachname': 'Schmidt',
                'email': 'klaus.schmidt@testfacility.local',
                'role': 'PFLEGEFACHKRAFT',
                'is_active': True,
                'can_administer_btm': True
            },
            {
                'vorname': 'Petra',
                'nachname': 'Weber',
                'email': 'petra.weber@testfacility.local',
                'role': 'PFLEGEHILFSKRAFT',
                'is_active': True,
                'can_administer_btm': False
            }
        ]

        employees = []
        for emp_data in employees_data:
            emp = Employee(
                company_id=company.id,
                **emp_data
            )
            emp.set_password('password123')
            emp.set_pin('1234')
            db.session.add(emp)
            employees.append(emp)
            print(f"[OK] Created employee: {emp.full_name}")

        db.session.commit()

        # Create test patients
        patients_data = [
            {
                'vorname': 'Hans',
                'nachname': 'Mueller',
                'pflegegrad': '2',
                'aufnahmedatum': date.today() - timedelta(days=30),
                'zimmer_nr': '101',
                'sturzrisiko': True,
                'dekubitusrisiko': False,
                'ernaehrungsrisiko': False
            },
            {
                'vorname': 'Greta',
                'nachname': 'Schmidt',
                'pflegegrad': '3',
                'aufnahmedatum': date.today() - timedelta(days=15),
                'zimmer_nr': '102',
                'sturzrisiko': False,
                'dekubitusrisiko': True,
                'ernaehrungsrisiko': True
            },
            {
                'vorname': 'Otto',
                'nachname': 'Bauer',
                'pflegegrad': '4',
                'aufnahmedatum': date.today() - timedelta(days=5),
                'zimmer_nr': '103',
                'sturzrisiko': True,
                'dekubitusrisiko': True,
                'ernaehrungsrisiko': False
            }
        ]

        patients = []
        for patient_data in patients_data:
            patient = Patient(
                company_id=company.id,
                status='AKTIV',
                **patient_data
            )
            db.session.add(patient)
            patients.append(patient)
            print(f"[OK] Created patient: {patient.full_name}")

        db.session.commit()

    # Create test services (always ensure they exist)
    print(f"\n[SETUP] Creating test services")
    services_data = [
        {'kategorie': 'Körperpflege', 'bezeichnung': 'Ganzkörperwäsche', 'dauer_minuten': 30, 'preis': 25.00},
        {'kategorie': 'Körperpflege', 'bezeichnung': 'Teilwäsche', 'dauer_minuten': 15, 'preis': 15.00},
        {'kategorie': 'Körperpflege', 'bezeichnung': 'Haarpflege', 'dauer_minuten': 20, 'preis': 12.00},
        {'kategorie': 'Mobilisation', 'bezeichnung': 'Mobilisation Bett-Rollstuhl', 'dauer_minuten': 10, 'preis': 8.00},
        {'kategorie': 'Mobilisation', 'bezeichnung': 'Gehtraining', 'dauer_minuten': 20, 'preis': 12.00},
        {'kategorie': 'Ernährung', 'bezeichnung': 'Unterstützung bei Mahlzeiten', 'dauer_minuten': 30, 'preis': 15.00},
        {'kategorie': 'Behandlungspflege', 'bezeichnung': 'Wundversorgung', 'dauer_minuten': 25, 'preis': 20.00},
        {'kategorie': 'Behandlungspflege', 'bezeichnung': 'Medikamentengabe', 'dauer_minuten': 10, 'preis': 5.00},
    ]

    for i, svc_data in enumerate(services_data):
        existing = Leistungskatalog.query.filter_by(
            company_id=company.id,
            bezeichnung=svc_data['bezeichnung']
        ).first()

        if existing:
            print(f"[INFO] Service #{i+1} already exists")
        else:
            svc = Leistungskatalog(
                company_id=company.id,
                leistung_nr=f"LK{i+1:02d}",
                **svc_data
            )
            db.session.add(svc)
            print(f"[OK] Created service #{i+1}")

    db.session.commit()
    return company, employees, patients


def test_required_fields():
    """Test 1: Required field highlighting and validation."""
    print("\n" + "="*70)
    print("TEST 1: Required Fields & Missing Documentation Alerts")
    print("="*70)

    company = Company.query.filter_by(name='Test Facility').first()
    patients = Patient.query.filter_by(company_id=company.id).all()

    print(f"\nChecking {len(patients)} patients for missing critical documentation:")

    for patient in patients:
        # Check SIS assessment
        sis = SisAssessment.query.filter_by(patient_id=patient.id, is_current=True).first()
        sis_status = "OK" if sis else "MISSING"

        # Check wound documentation for high-risk patients
        wound_needed = patient.dekubitusrisiko or patient.sturzrisiko
        wound_status = "N/A"
        if wound_needed:
            from app.models import WoundDoc
            wound = WoundDoc.query.filter_by(patient_id=patient.id, is_active=True).first()
            wound_status = "OK" if wound else "MISSING"

        print(f"\n  Patient: {patient.full_name} (PG {patient.pflegegrad}, Zimmer {patient.zimmer_nr})")
        print(f"    - SIS Assessment: [{sis_status}]")
        if wound_needed:
            print(f"    - Wound Documentation (risk patient): [{wound_status}]")
        print(f"    - High risk: Sturz={patient.sturzrisiko}, Dekubitus={patient.dekubitusrisiko}")


def test_pdf_generation():
    """Test 2: PDF export functionality."""
    print("\n" + "="*70)
    print("TEST 2: PDF Export Generation")
    print("="*70)

    from app.utils.pdf import (
        generate_patient_summary_pdf,
        generate_sis_assessment_pdf,
        generate_medication_plan_pdf
    )

    company = Company.query.filter_by(name='Test Facility').first()
    patients = Patient.query.filter_by(company_id=company.id).limit(1).all()

    if not patients:
        print("[SKIP] No test patients found")
        return

    patient = patients[0]
    print(f"\nTesting PDF generation for patient: {patient.full_name}")

    # Test patient summary PDF
    try:
        pdf_buffer = generate_patient_summary_pdf(patient)
        pdf_data = pdf_buffer.getvalue()
        print(f"  [OK] Patient Summary PDF: {len(pdf_data)} bytes")
    except Exception as e:
        print(f"  [ERROR] Patient Summary PDF: {str(e)}")

    # Test SIS assessment PDF (if exists)
    sis = SisAssessment.query.filter_by(patient_id=patient.id, is_current=True).first()
    if sis:
        try:
            pdf_buffer = generate_sis_assessment_pdf(patient, sis)
            pdf_data = pdf_buffer.getvalue()
            print(f"  [OK] SIS Assessment PDF: {len(pdf_data)} bytes")
        except Exception as e:
            print(f"  [ERROR] SIS Assessment PDF: {str(e)}")
    else:
        print(f"  [SKIP] SIS Assessment PDF: No SIS assessment found")

    # Test medication plan PDF (if exists)
    plan = MedicationPlan.query.filter_by(patient_id=patient.id, is_current=True).first()
    if plan:
        try:
            pdf_buffer = generate_medication_plan_pdf(patient, plan)
            pdf_data = pdf_buffer.getvalue()
            print(f"  [OK] Medication Plan PDF: {len(pdf_data)} bytes")
        except Exception as e:
            print(f"  [ERROR] Medication Plan PDF: {str(e)}")
    else:
        print(f"  [SKIP] Medication Plan PDF: No medication plan found")


def test_email_system():
    """Test 3: Email system configuration."""
    print("\n" + "="*70)
    print("TEST 3: Email System Configuration")
    print("="*70)

    from flask import current_app
    from app.utils.email import (
        send_patient_admission_email,
        send_btm_alert_email,
        send_missing_documentation_alert
    )

    print("\nEmail Configuration:")
    print(f"  Server: {current_app.config.get('MAIL_SERVER')}")
    print(f"  Port: {current_app.config.get('MAIL_PORT')}")
    print(f"  TLS: {current_app.config.get('MAIL_USE_TLS')}")
    print(f"  Username: {current_app.config.get('MAIL_USERNAME') or 'NOT SET'}")
    print(f"  Default Sender: {current_app.config.get('MAIL_DEFAULT_SENDER')}")

    username = current_app.config.get('MAIL_USERNAME')
    password = current_app.config.get('MAIL_PASSWORD')

    if not username or not password:
        print("\n  [WARNING] Email credentials not configured")
        print("  To test email sending, set MAIL_USERNAME and MAIL_PASSWORD in .env")
        return

    print("\n  [OK] SMTP credentials configured")

    # Test email functions are callable
    company = Company.query.filter_by(name='Test Facility').first()
    employees = Employee.query.filter_by(company_id=company.id).limit(1).all()
    patients = Patient.query.filter_by(company_id=company.id).limit(1).all()

    if employees and patients:
        emp = employees[0]
        pat = patients[0]

        # Show what would be sent (don't actually send)
        print(f"\n  Test email recipients:")
        print(f"    To: {emp.email}")
        print(f"    Patient: {pat.full_name}")
        print(f"\n  NOTE: Email sending disabled in test mode")
        print(f"  To enable: Configure MAIL_USERNAME and MAIL_PASSWORD, then emails will send automatically on:")
        print(f"    - Patient creation")
        print(f"    - BtM medication administration")
        print(f"    - POST /alerts/check-missing-docs endpoint")


def test_onboarding():
    """Test 4: First-login onboarding."""
    print("\n" + "="*70)
    print("TEST 4: Onboarding & First-Login Detection")
    print("="*70)

    company = Company.query.filter_by(name='Test Facility').first()

    # Create a new employee without last_login
    new_emp = Employee(
        company_id=company.id,
        vorname='Test',
        nachname='Onboard',
        email='test.onboard@testfacility.local',
        role='PFLEGEHILFSKRAFT',
        is_active=True,
        last_login_at=None  # No login yet
    )
    new_emp.set_password('password123')

    existing = Employee.query.filter_by(email=new_emp.email).first()
    if not existing:
        db.session.add(new_emp)
        db.session.commit()
        print(f"[OK] Created test onboarding employee: {new_emp.full_name}")
        print(f"     First-login flag: {new_emp.last_login_at is None}")
    else:
        print(f"[INFO] Onboarding test employee already exists")
        print(f"       First-login flag: {existing.last_login_at is None}")

    # Show what would happen on first login
    print(f"\n  On first login, new staff would see:")
    print(f"    - Onboarding tooltip with system overview")
    print(f"    - Dashboard alert with missing documentation summary")
    print(f"    - Redirect to #onboarding anchor for visibility")


def run_all_tests():
    """Run all workflow tests."""
    app = create_app()

    with app.app_context():
        print("\n" + "="*70)
        print("PflegeOS - END-TO-END WORKFLOW TESTING")
        print("="*70)

        # Setup
        company, employees, patients = setup_test_data()

        # Run tests
        test_required_fields()
        test_pdf_generation()
        test_email_system()
        test_onboarding()

        # Summary
        print("\n" + "="*70)
        print("TESTING SUMMARY")
        print("="*70)
        print(f"\nTest Company: {company.name}")
        print(f"Test Employees: {len(employees)}")
        for emp in employees:
            print(f"  - {emp.full_name} ({emp.role}) - {emp.email}")
        print(f"Test Patients: {len(patients)}")
        for pat in patients:
            print(f"  - {pat.full_name} (Zimmer {pat.zimmer_nr}, PG {pat.pflegegrad})")

        print("\n" + "="*70)
        print("NEXT STEPS:")
        print("="*70)
        print("""
1. Login to dashboard with test credentials:
   - Email: anna.mueller@testfacility.local
   - Password: password123
   - PIN: 1234

2. Create a medication plan for a test patient:
   - Go to Patients > Patient > Medikamente
   - Add medications including a BtM-marked medication

3. Test BtM administration:
   - Click "Verabreichen" on medication
   - Fill form with device ID and PIN
   - Verify alert email would be sent

4. Check PDF exports:
   - Patient profile > PDF button (patient summary)
   - SIS assessment > PDF button
   - Medication plan > PDF button

5. For email testing:
   - Set MAIL_USERNAME and MAIL_PASSWORD in .env
   - Create new patient (triggers admission email)
   - Administer BtM medication (triggers BtM alert)
   - POST /alerts/check-missing-docs as admin (triggers alert)
        """)

        print("="*70 + "\n")


if __name__ == '__main__':
    run_all_tests()
