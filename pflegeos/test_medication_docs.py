import sys
sys.path.insert(0, '.')

from app import create_app, db
from app.models import Company, Patient, MedicationPlan, Medication, MedicationDocument, Employee
from datetime import date
from app.routes.medications import _create_medication_document

app = create_app('development')

with app.app_context():
    # Check if test company exists
    company = Company.query.filter_by(name='Test Company').first()
    if not company:
        company = Company(name='Test Company', stadt='Test Stadt')
        db.session.add(company)
        db.session.commit()
        print(f"✓ Created test company: {company.id}")
    else:
        print(f"✓ Found existing test company: {company.id}")
    
    # Check if test patient exists
    patient = Patient.query.filter_by(vorname='John', nachname='Doe').first()
    if not patient:
        patient = Patient(
            company_id=company.id,
            vorname='John',
            nachname='Doe',
            geburtsdatum=date(1980, 1, 1)
        )
        db.session.add(patient)
        db.session.commit()
        print(f"✓ Created test patient: {patient.id}")
    else:
        print(f"✓ Found existing test patient: {patient.id}")
    
    # Create a test medication plan
    plan = MedicationPlan(
        company_id=company.id,
        patient_id=patient.id,
        created_by=1,  # Assuming employee 1 exists
        prescribed_by='Dr. Test',
        valid_from=date.today()
    )
    db.session.add(plan)
    db.session.commit()
    print(f"✓ Created medication plan: {plan.id}")
    
    # Add medications
    med1 = Medication(
        medication_plan_id=plan.id,
        handelsname='Aspirin',
        wirkstoff='Acetylsalicylsäure',
        staerke='500mg',
        darreichungsform='Tablette',
        morgens='1',
        mittags='0',
        abends='1',
        nachts='0'
    )
    med2 = Medication(
        medication_plan_id=plan.id,
        handelsname='Ibuprofen',
        wirkstoff='Ibuprofen',
        staerke='400mg',
        darreichungsform='Tablette',
        morgens='0',
        mittags='1',
        abends='0',
        nachts='0',
        is_btm=True,
        btm_bestand=10.0
    )
    db.session.add(med1)
    db.session.add(med2)
    db.session.commit()
    print(f"✓ Added medications to plan")
    
    # Generate medication document
    _create_medication_document(plan)
    print(f"✓ Generated medication document")
    
    # Verify document was created
    doc = MedicationDocument.query.filter_by(medication_plan_id=plan.id).first()
    if doc:
        print(f"✓ Document created successfully:")
        print(f"  - ID: {doc.id}")
        print(f"  - Title: {doc.title}")
        print(f"  - Status: {doc.status}")
        print(f"  - Content length: {len(doc.content)} chars")
        print(f"\n✓ Medication document automation is WORKING!")
    else:
        print("✗ Document not found!")
        
    # Verify we can query documents for the patient
    docs = MedicationDocument.query.filter_by(patient_id=patient.id).all()
    print(f"\n✓ Found {len(docs)} document(s) for patient {patient.id}")

