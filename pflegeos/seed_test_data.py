#!/usr/bin/env python
"""
seed_test_data.py — Создает тестовые данные для Claude API и schedule generation
Использование: flask shell < seed_test_data.py  или  python seed_test_data.py
"""
from app import create_app
from app.extensions import db
from app.models import (
    Company, Employee, Patient, Procedure, EmployeeSchedule, VisitReport,
    EmployeePatientAssignment
)
from datetime import datetime, date, timedelta
import time

app = create_app()
ctx = app.app_context()
ctx.push()

print("🌱 Создание тестовых данных...")

# ============================================================
# 1. Компания
# ============================================================
timestamp = int(time.time() * 1000)  # Milliseconds for uniqueness
company = Company(
    name="Pflege Berlin Mitte",
    name_zusatz="Ambulanter Pflegedienst",
    company_type="AMBULANT",
    strasse="Friedrichstraße",
    hausnummer="123",
    plz="10115",
    ort="Berlin",
    bundesland="Berlin",
    email=f"info+{timestamp}@pflegeberlin.de",
    telefon="+49 30 12345678",
    plaetze_anzahl=50,
    geschaeftsfuehrer_name="Dr. Hans Müller",
)
db.session.add(company)
db.session.commit()
print(f"✅ Компания создана: {company.name}")

# ============================================================
# 2. Сотрудники (медсестры)
# ============================================================
employees_data = [
    {
        "vorname": "Sarah",
        "nachname": "Müller",
        "email": f"sarah.mueller+{timestamp}@pflegeberlin.de",
        "telefon": "+49 30 111-1111",
        "role": "PFLEGEFACHKRAFT",
        "qualification": "Pflegefachfrau",
    },
    {
        "vorname": "Tom",
        "nachname": "Schmidt",
        "email": f"tom.schmidt+{timestamp}@pflegeberlin.de",
        "telefon": "+49 30 111-2222",
        "role": "PFLEGEFACHKRAFT",
        "qualification": "Pflegefachkraft",
    },
    {
        "vorname": "Anna",
        "nachname": "Weber",
        "email": f"anna.weber+{timestamp}@pflegeberlin.de",
        "telefon": "+49 30 111-3333",
        "role": "PFLEGEHILFSKRAFT",
        "qualification": "Pflegehelferin",
    },
]

employees = []
for emp_data in employees_data:
    emp = Employee(
        company_id=company.id,
        vorname=emp_data["vorname"],
        nachname=emp_data["nachname"],
        email=emp_data["email"],
        telefon=emp_data["telefon"],
        role=emp_data["role"],
        qualification=emp_data["qualification"],
    )
    db.session.add(emp)
    employees.append(emp)

db.session.commit()
print(f"✅ Созданы {len(employees)} сотрудников")

# ============================================================
# 3. Пациенты
# ============================================================
patients_data = [
    {
        "vorname": "Maria",
        "nachname": "Krämer",
        "geburtsdatum": date(1945, 3, 15),
        "betreuer_name": "Tochter - Maria Krämer",
        "betreuer_telefon": "+49 30 222-1111",
        "strasse": "Alexanderplatz",
        "hausnummer": "5",
        "pflegegrad": "3",
    },
    {
        "vorname": "Walter",
        "nachname": "Bauer",
        "geburtsdatum": date(1940, 7, 22),
        "betreuer_name": "Sohn - Klaus Bauer",
        "betreuer_telefon": "+49 30 222-2222",
        "strasse": "Torstraße",
        "hausnummer": "42",
        "pflegegrad": "4",
    },
    {
        "vorname": "Herta",
        "nachname": "Fischer",
        "geburtsdatum": date(1938, 11, 8),
        "betreuer_name": "Enkelin - Anna Fischer",
        "betreuer_telefon": "+49 30 222-3333",
        "strasse": "Straße des 17. Juni",
        "hausnummer": "100",
        "pflegegrad": "2",
    },
    {
        "vorname": "Hans",
        "nachname": "Richter",
        "geburtsdatum": date(1950, 1, 10),
        "betreuer_name": "Ehepartner - Gerda Richter",
        "betreuer_telefon": "+49 30 222-4444",
        "strasse": "Havelberger Straße",
        "hausnummer": "25",
        "pflegegrad": "2",
    },
]

patients = []
for pat_data in patients_data:
    pat = Patient(
        company_id=company.id,
        vorname=pat_data["vorname"],
        nachname=pat_data["nachname"],
        geburtsdatum=pat_data["geburtsdatum"],
        betreuer_name=pat_data["betreuer_name"],
        betreuer_telefon=pat_data["betreuer_telefon"],
        strasse=pat_data["strasse"],
        hausnummer=pat_data["hausnummer"],
        pflegegrad=pat_data["pflegegrad"],
    )
    db.session.add(pat)
    patients.append(pat)

db.session.commit()
print(f"✅ Созданы {len(patients)} пациентов")

# ============================================================
# 4. Процедуры (Leistungen)
# ============================================================
procedures_data = [
    {
        "name": "Vollbad / Dusche",
        "category": "CARE",
        "duration_minutes": 30,
        "description": "Gründliche Körperpflege mit Vollbad oder Dusche",
        "required_qualification": "PFLEGEFACHKRAFT",
        "requires_verification": True,
    },
    {
        "name": "Medikamentengabe",
        "category": "MEDICATION",
        "duration_minutes": 10,
        "description": "Verabreichung von Medikamenten nach ärztlicher Anordnung",
        "required_qualification": "PFLEGEFACHKRAFT",
        "requires_verification": True,
    },
    {
        "name": "Verbandwechsel",
        "category": "WOUND",
        "duration_minutes": 20,
        "description": "Wechsel und Versorgung von Wundverbänden",
        "required_qualification": "PFLEGEFACHKRAFT",
        "requires_verification": True,
    },
    {
        "name": "Blutdruckmessung",
        "category": "MONITORING",
        "duration_minutes": 5,
        "description": "Regelmäßige Kontrolle des Blutdrucks",
        "required_qualification": None,
        "requires_verification": False,
    },
    {
        "name": "Mobilisation / Transfer",
        "category": "MOBILITY",
        "duration_minutes": 15,
        "description": "Unterstützung bei Bewegung und Lagewechsel",
        "required_qualification": None,
        "requires_verification": False,
    },
    {
        "name": "Essen reichen",
        "category": "NUTRITION",
        "duration_minutes": 20,
        "description": "Unterstützung bei der Nahrungsaufnahme",
        "required_qualification": None,
        "requires_verification": False,
    },
]

procedures = []
for proc_data in procedures_data:
    proc = Procedure(
        company_id=company.id,
        name=proc_data["name"],
        category=proc_data["category"],
        duration_minutes=proc_data["duration_minutes"],
        description=proc_data["description"],
        required_qualification=proc_data["required_qualification"],
        requires_verification=proc_data["requires_verification"],
    )
    db.session.add(proc)
    procedures.append(proc)

db.session.commit()
print(f"✅ Созданы {len(procedures)} процедур")

# ============================================================
# 5. Назначения сотрудников пациентам
# ============================================================
for i, patient in enumerate(patients):
    # Каждому пациенту назначаем 1-2 основных медсестер
    assigned_emps = employees[: (i % 2) + 1]
    for emp in assigned_emps:
        assignment = EmployeePatientAssignment(
            company_id=company.id,
            employee_id=emp.id,
            patient_id=patient.id,
            role="PRIMARY_NURSE",
        )
        db.session.add(assignment)

db.session.commit()
print(f"✅ Созданы назначения сотрудников пациентам")

# ============================================================
# Вывод информации
# ============================================================
print("\n" + "=" * 60)
print("📊 ТЕСТОВЫЕ ДАННЫЕ СОЗДАНЫ")
print("=" * 60)
print(f"Компания: {company.name} ({company.id})")
print(f"Сотрудников: {len(employees)}")
for emp in employees:
    print(f"  - {emp.full_name} ({emp.role})")
print(f"Пациентов: {len(patients)}")
for pat in patients:
    print(f"  - {pat.full_name} (Pflegegrad {pat.pflegegrad})")
print(f"Процедур: {len(procedures)}")
for proc in procedures:
    print(f"  - {proc.name} ({proc.duration_minutes}min)")

print("\n✅ Готово! Можно тестировать Claude API")
print(f"\n📱 Сотрудники для логина:")
for emp in employees:
    print(f"   {emp.email}")

ctx.pop()
