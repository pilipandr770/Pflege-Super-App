import sys
sys.path.insert(0, '.')

from app import create_app, db
from app.models import MedicationPlan, Medication, MedicationDocument, Patient
from app.routes.medications import _create_medication_document
from datetime import date

app = create_app('development')

with app.app_context():
    # Get the existing patient
    patient = Patient.query.filter_by(vorname='Max', nachname='Mueller').first()
    if not patient:
        print("ERROR: Patient not found")
        exit(1)
    
    print(f"FOUND: Patient {patient.vorname} {patient.nachname}")
    
    # Get the existing medication plan
    plan = MedicationPlan.query.filter_by(patient_id=patient.id).first()
    if not plan:
        print("ERROR: No medication plan found")
        exit(1)
    
    print(f"FOUND: Medication plan {plan.id}")
    
    # Add test medications if missing
    existing_meds = Medication.query.filter_by(medication_plan_id=plan.id).count()
    if existing_meds == 0:
        med1 = Medication(
            medication_plan_id=plan.id,
            handelsname='Paracetamol',
            wirkstoff='Paracetamol',
            staerke='500mg',
            darreichungsform='Tablette',
            morgens='1',
            mittags='0',
            abends='1',
            nachts='0'
        )
        db.session.add(med1)
        db.session.commit()
        print("ADDED: Test medication")
    
    # Generate medication document
    _create_medication_document(plan)
    print("CALLED: Document generation function")
    
    # Verify document was created
    doc = MedicationDocument.query.filter_by(medication_plan_id=plan.id).first()
    
    if doc:
        print(f"SUCCESS: Document created - ID: {doc.id}")
        print(f"TITLE: {doc.title}")
        print(f"STATUS: {doc.status}")
        if 'Paracetamol' in doc.content:
            print("VERIFIED: Medication appears in document content")
    else:
        print("ERROR: Document not created")
        exit(1)

