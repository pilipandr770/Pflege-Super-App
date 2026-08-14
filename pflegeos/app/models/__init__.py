import uuid
from datetime import datetime, date
from flask_login import UserMixin
from app.extensions import db, bcrypt


def gen_uuid():
    return str(uuid.uuid4())


# ============================================================
# ENUMS (строки вместо PostgreSQL ENUM для переносимости)
# ============================================================
# company_type: STATIONAER | AMBULANT | TEILSTATIONAER | BETREUTES_WOHNEN
# company_status: PENDING | VERIFIED | ACTIVE | SUSPENDED | CANCELLED
# subscription_plan: TRIAL | STARTER | PRO | PREMIUM
# employee_role: ADMIN | PFLEGEFACHKRAFT | PFLEGEHILFSKRAFT | BEHANDLUNGSPFLEGE | HAUSWIRTSCHAFT | FAHRER | VERWALTUNG
# pflegegrad: 1 | 2 | 3 | 4 | 5
# patient_status: AKTIV | BEURLAUBT | VERSTORBEN | AUSGEZOGEN
# document_status: DRAFT | COMPLETED | VERIFIED | LOCKED
# verification_method: MAC_GPS | MAC_GPS_NFC | PIN_MAC_GPS | DUAL_PIN | MANUAL_SIGNATURE


# ============================================================
# COMPANY
# ============================================================
class Company(db.Model):
    __tablename__ = 'companies'

    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    name = db.Column(db.String(255), nullable=False)
    name_zusatz = db.Column(db.String(255))
    rechtsform = db.Column(db.String(100))
    handelsregister_nr = db.Column(db.String(50))
    handelsregister_gericht = db.Column(db.String(100))
    steuernummer = db.Column(db.String(50))
    ust_id = db.Column(db.String(20))
    heimaufsicht_nr = db.Column(db.String(100))
    ik_nummer = db.Column(db.String(15))
    company_type = db.Column(db.String(30), nullable=False, default='STATIONAER')
    plaetze_anzahl = db.Column(db.Integer)

    # Адрес
    strasse = db.Column(db.String(255), nullable=False)
    hausnummer = db.Column(db.String(20), nullable=False)
    plz = db.Column(db.String(10), nullable=False)
    ort = db.Column(db.String(100), nullable=False)
    bundesland = db.Column(db.String(50), nullable=False)

    # Контакты
    telefon = db.Column(db.String(50))
    email = db.Column(db.String(255), nullable=False, unique=True)
    website = db.Column(db.String(255))

    # Ответственные
    geschaeftsfuehrer_name = db.Column(db.String(255))
    pdl_name = db.Column(db.String(255))
    datenschutz_name = db.Column(db.String(255))
    datenschutz_email = db.Column(db.String(255))

    # SaaS статус
    status = db.Column(db.String(20), default='PENDING')
    plan = db.Column(db.String(20), default='TRIAL')
    trial_ends_at = db.Column(db.DateTime)
    verified_at = db.Column(db.DateTime)

    # Stripe
    stripe_customer_id     = db.Column(db.String(100), unique=True)  # cus_xxx
    stripe_subscription_id = db.Column(db.String(100), unique=True)  # sub_xxx
    subscription_status    = db.Column(db.String(30))                # active | past_due | canceled | trialing
    current_period_end     = db.Column(db.DateTime)                  # next billing date

    slug = db.Column(db.String(100), unique=True)
    logo_url = db.Column(db.Text)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    deleted_at = db.Column(db.DateTime)

    # Relations
    employees = db.relationship('Employee', backref='company', lazy='dynamic')
    patients = db.relationship('Patient', backref='company', lazy='dynamic')

    def __repr__(self):
        return f'<Company {self.name}>'


# ============================================================
# EMPLOYEE
# ============================================================
class Employee(db.Model, UserMixin):
    __tablename__ = 'employees'

    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    company_id = db.Column(db.String(36), db.ForeignKey('companies.id'), nullable=False)

    vorname = db.Column(db.String(100), nullable=False)
    nachname = db.Column(db.String(100), nullable=False)
    geburtsdatum = db.Column(db.Date)
    gender = db.Column(db.String(1))
    email = db.Column(db.String(255), unique=True)
    telefon = db.Column(db.String(50))

    role = db.Column(db.String(30), nullable=False, default='PFLEGEHILFSKRAFT')
    qualification = db.Column(db.String(50))
    einstellungsdatum = db.Column(db.Date)
    personalnummer = db.Column(db.String(50))

    # Führerschein
    fuehrerschein_klasse = db.Column(db.String(30))   # z.B. "B, BE"
    fuehrerschein_bis    = db.Column(db.Date)

    # Auth
    password_hash = db.Column(db.Text)
    pin_hash = db.Column(db.Text)
    last_login_at = db.Column(db.DateTime)

    # Разрешения
    can_administer_btm = db.Column(db.Boolean, default=False)
    can_wound_care = db.Column(db.Boolean, default=False)
    can_approve_documents = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    is_superadmin = db.Column(db.Boolean, default=False)  # Platform super-admin

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    deleted_at = db.Column(db.DateTime)

    def set_password(self, password):
        self.password_hash = bcrypt.generate_password_hash(password).decode('utf-8')

    def check_password(self, password):
        return bcrypt.check_password_hash(self.password_hash, password)

    def set_pin(self, pin):
        self.pin_hash = bcrypt.generate_password_hash(pin).decode('utf-8')

    def check_pin(self, pin):
        return bcrypt.check_password_hash(self.pin_hash, pin)

    @property
    def full_name(self):
        return f'{self.vorname} {self.nachname}'

    @property
    def is_admin(self):
        return self.role == 'ADMIN' or bool(self.is_superadmin)

    # --- Rolle-Helfer für Template-Navigation ---

    @property
    def is_field_staff(self):
        """Außendienstmitarbeiter — brauchen Dienstplan + Berichte."""
        return self.role in (
            'PFLEGEFACHKRAFT', 'PFLEGEHILFSKRAFT',
            'BEHANDLUNGSPFLEGE', 'HAUSWIRTSCHAFT', 'FAHRER'
        )

    @property
    def is_care_role(self):
        """Pflegende Rollen — dürfen Leistungsnachweise erfassen."""
        return self.role in (
            'PFLEGEFACHKRAFT', 'PFLEGEHILFSKRAFT', 'BEHANDLUNGSPFLEGE'
        )

    @property
    def is_office_role(self):
        """Verwaltung — Lesezugriff auf Patienten / Mitarbeiter."""
        return self.role == 'VERWALTUNG'

    @property
    def can_see_btm(self):
        """BtM-Buch: Admins, Fachkräfte und wer die Berechtigung hat."""
        return self.role in ('ADMIN', 'PFLEGEFACHKRAFT', 'BEHANDLUNGSPFLEGE') \
               or bool(self.can_administer_btm)

    @property
    def role_label(self):
        """Lesbarer Rollenname für die UI."""
        labels = {
            'ADMIN':             'Administrator',
            'PFLEGEFACHKRAFT':   'Pflegefachkraft',
            'PFLEGEHILFSKRAFT':  'Pflegehilfskraft',
            'BEHANDLUNGSPFLEGE': 'Behandlungspflege',
            'HAUSWIRTSCHAFT':    'Hauswirtschaft',
            'FAHRER':            'Fahrer/in',
            'VERWALTUNG':        'Verwaltung',
        }
        return labels.get(self.role, self.role)

    @property
    def fuehrerschein_tage(self):
        if not self.fuehrerschein_bis:
            return None
        return (self.fuehrerschein_bis - date.today()).days

    @property
    def fuehrerschein_status(self):
        t = self.fuehrerschein_tage
        if t is None:   return 'unknown'
        if t < 0:       return 'expired'
        if t <= 30:     return 'critical'
        if t <= 90:     return 'warning'
        return 'ok'

    def __repr__(self):
        return f'<Employee {self.full_name}>'


# ============================================================
# DEVICE
# ============================================================
class Device(db.Model):
    __tablename__ = 'devices'

    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    company_id = db.Column(db.String(36), db.ForeignKey('companies.id'), nullable=False)
    employee_id = db.Column(db.String(36), db.ForeignKey('employees.id'))

    mac_address = db.Column(db.String(17), nullable=False)
    device_name = db.Column(db.String(255))
    device_model = db.Column(db.String(255))
    os_version = db.Column(db.String(100))
    app_version = db.Column(db.String(50))

    is_active = db.Column(db.Boolean, default=True)
    last_seen_at = db.Column(db.DateTime)
    last_ip = db.Column(db.String(45))
    last_lat = db.Column(db.Float)
    last_lng = db.Column(db.Float)

    registered_at = db.Column(db.DateTime, default=datetime.utcnow)
    deactivated_at = db.Column(db.DateTime)


# ============================================================
# PATIENT
# ============================================================
class Patient(db.Model):
    __tablename__ = 'patients'

    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    company_id = db.Column(db.String(36), db.ForeignKey('companies.id'), nullable=False)
    ai_token = db.Column(db.String(36), default=gen_uuid, unique=True)

    # Персональные данные
    vorname = db.Column(db.String(100), nullable=False)
    nachname = db.Column(db.String(100), nullable=False)
    geburtsdatum = db.Column(db.Date)
    gender = db.Column(db.String(1))
    nationalitaet = db.Column(db.String(100))
    religion = db.Column(db.String(100))
    sprache_muttersprache = db.Column(db.String(100))

    # Адрес (для домашнего ухода)
    strasse = db.Column(db.String(255))
    hausnummer = db.Column(db.String(20))
    plz = db.Column(db.String(10))
    ort = db.Column(db.String(100))
    bundesland = db.Column(db.String(50))

    # Контакты
    betreuer_name = db.Column(db.String(255))
    betreuer_telefon = db.Column(db.String(50))
    betreuer_verhaeltnis = db.Column(db.String(100))
    betreuer_email = db.Column(db.String(255))      # E-Mail des Angehörigen
    hausarzt_name = db.Column(db.String(255))
    hausarzt_telefon = db.Column(db.String(50))

    # Angehörigen-Portal (Magic-Link-Zugang)
    portal_token = db.Column(db.String(36), default=gen_uuid, unique=True)
    portal_enabled = db.Column(db.Boolean, default=False)
    portal_sprache = db.Column(db.String(5), default='de')  # de / ru / en

    # Hausarzt-Portal (Magic-Link für externen Arzt)
    arzt_token = db.Column(db.String(36), default=gen_uuid, unique=True)
    arzt_portal_enabled = db.Column(db.Boolean, default=False)
    arzt_last_update = db.Column(db.DateTime)   # letzter Arzt-Eingriff

    # Тип обслуживания (домашний уход или стационар)
    care_type = db.Column(db.String(30), default='HOME_CARE')  # HOME_CARE | INPATIENT

    # Pflege
    pflegegrad = db.Column(db.String(1))
    pflegegrad_seit = db.Column(db.Date)
    zimmer_nr = db.Column(db.String(20))  # Только для стационара
    bett_nr = db.Column(db.String(20))    # Только для стационара
    aufnahmedatum = db.Column(db.Date)
    entlassungsdatum = db.Column(db.Date)
    status = db.Column(db.String(20), default='AKTIV')

    # Krankenkasse
    krankenversicherung = db.Column(db.String(255))
    versicherungsnummer = db.Column(db.String(100))

    # Медицинские данные
    allergien = db.Column(db.Text)
    gewicht_kg = db.Column(db.Float)
    groesse_cm = db.Column(db.Integer)
    blutgruppe = db.Column(db.String(5))

    # Риски
    sturzrisiko = db.Column(db.Boolean, default=False)
    dekubitusrisiko = db.Column(db.Boolean, default=False)
    ernaehrungsrisiko = db.Column(db.Boolean, default=False)

    # Согласия
    einwilligung_foto = db.Column(db.Boolean, default=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    deleted_at = db.Column(db.DateTime)

    @property
    def full_name(self):
        return f'{self.vorname} {self.nachname}'

    @property
    def age(self):
        if self.geburtsdatum:
            today = date.today()
            return today.year - self.geburtsdatum.year - (
                (today.month, today.day) < (self.geburtsdatum.month, self.geburtsdatum.day)
            )
        return None

    def __repr__(self):
        return f'<Patient {self.full_name}>'


# ============================================================
# EMPLOYEE PATIENT ASSIGNMENT
# ============================================================
class EmployeePatientAssignment(db.Model):
    __tablename__ = 'employee_patient_assignments'

    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    company_id = db.Column(db.String(36), db.ForeignKey('companies.id'), nullable=False)
    employee_id = db.Column(db.String(36), db.ForeignKey('employees.id'), nullable=False)
    patient_id = db.Column(db.String(36), db.ForeignKey('patients.id'), nullable=False)

    # Роль в уходе за пациентом
    role = db.Column(db.String(50), default='PRIMARY_NURSE')  # PRIMARY_NURSE, SECONDARY_NURSE, CAREGIVER

    # Когда назначена
    assigned_at = db.Column(db.DateTime, default=datetime.utcnow)
    assigned_by = db.Column(db.String(36), db.ForeignKey('employees.id'))

    # Отзыв
    unassigned_at = db.Column(db.DateTime)
    unassigned_by = db.Column(db.String(36), db.ForeignKey('employees.id'))

    is_active = db.Column(db.Boolean, default=True)
    notes = db.Column(db.Text)

    # Relations
    employee = db.relationship('Employee', foreign_keys=[employee_id], backref='patient_assignments')
    patient = db.relationship('Patient', backref='employee_assignments')

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<Assignment {self.employee.full_name} → {self.patient.full_name}>'


# ============================================================
# SIS
# ============================================================
class SisAssessment(db.Model):
    __tablename__ = 'sis_assessments'

    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    company_id = db.Column(db.String(36), db.ForeignKey('companies.id'), nullable=False)
    patient_id = db.Column(db.String(36), db.ForeignKey('patients.id'), nullable=False)
    created_by = db.Column(db.String(36), db.ForeignKey('employees.id'), nullable=False)
    approved_by = db.Column(db.String(36), db.ForeignKey('employees.id'))
    version = db.Column(db.Integer, default=1)
    is_current = db.Column(db.Boolean, default=True)

    # Block 1: Kognition
    kb1_orientierung = db.Column(db.SmallInteger)
    kb1_gedaechtnis = db.Column(db.SmallInteger)
    kb1_verstehen = db.Column(db.SmallInteger)
    kb1_kommunikation = db.Column(db.SmallInteger)
    kb1_verhalten = db.Column(db.SmallInteger)
    kb1_freitext = db.Column(db.Text)

    # Block 2: Mobilität
    kb2_positionswechsel = db.Column(db.SmallInteger)
    kb2_transfer = db.Column(db.SmallInteger)
    kb2_gehen = db.Column(db.SmallInteger)
    kb2_treppensteigen = db.Column(db.SmallInteger)
    kb2_hilfsmittel = db.Column(db.Text)
    kb2_freitext = db.Column(db.Text)

    # Block 3: Krankheitsbezogen
    kb3_medikamente = db.Column(db.Text)
    kb3_injektionen = db.Column(db.Boolean, default=False)
    kb3_verbandwechsel = db.Column(db.Boolean, default=False)
    kb3_katheter = db.Column(db.Boolean, default=False)
    kb3_sonde = db.Column(db.Boolean, default=False)
    kb3_sauerstoff = db.Column(db.Boolean, default=False)
    kb3_freitext = db.Column(db.Text)

    # Block 4: Selbstversorgung
    kb4_koerperpflege = db.Column(db.SmallInteger)
    kb4_ernaehrung = db.Column(db.SmallInteger)
    kb4_trinken = db.Column(db.SmallInteger)
    kb4_ausscheidung = db.Column(db.SmallInteger)
    kb4_ankleiden = db.Column(db.SmallInteger)
    kb4_kostform = db.Column(db.String(100))
    kb4_freitext = db.Column(db.Text)

    # Block 5: Soziales
    kb5_soziale_kontakte = db.Column(db.Text)
    kb5_tagesstruktur = db.Column(db.Text)
    kb5_interessen = db.Column(db.Text)
    kb5_freitext = db.Column(db.Text)

    # Block 6: Haushaltsführung (ambulant)
    kb6_einkaufen = db.Column(db.SmallInteger)
    kb6_kochen = db.Column(db.SmallInteger)
    kb6_reinigung = db.Column(db.SmallInteger)
    kb6_freitext = db.Column(db.Text)

    # Итог
    pflegeschwerpunkte = db.Column(db.Text)
    ziele = db.Column(db.Text)
    besonderheiten = db.Column(db.Text)

    # Верификация
    verification_method = db.Column(db.String(30), default='PIN_MAC_GPS')
    device_mac = db.Column(db.String(17))
    geo_lat = db.Column(db.Float)
    geo_lng = db.Column(db.Float)

    status = db.Column(db.String(20), default='DRAFT')
    assessment_date = db.Column(db.Date, default=date.today)
    next_review_date = db.Column(db.Date)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    approved_at = db.Column(db.DateTime)
    locked_at = db.Column(db.DateTime)

    patient = db.relationship('Patient', backref='sis_assessments')
    creator = db.relationship('Employee', foreign_keys=[created_by])
    approver = db.relationship('Employee', foreign_keys=[approved_by])


# ============================================================
# MEDICATION PLAN
# ============================================================
class MedicationPlan(db.Model):
    __tablename__ = 'medication_plans'

    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    company_id = db.Column(db.String(36), db.ForeignKey('companies.id'), nullable=False)
    patient_id = db.Column(db.String(36), db.ForeignKey('patients.id'), nullable=False)
    created_by = db.Column(db.String(36), db.ForeignKey('employees.id'), nullable=True)
    prescribed_by = db.Column(db.String(255))

    valid_from = db.Column(db.Date, nullable=False, default=date.today)
    valid_until = db.Column(db.Date)
    is_current = db.Column(db.Boolean, default=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    patient = db.relationship('Patient', backref='medication_plans')
    creator = db.relationship('Employee', foreign_keys=[created_by])
    medications = db.relationship('Medication', backref='plan', lazy='dynamic')


class Medication(db.Model):
    __tablename__ = 'medications'

    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    medication_plan_id = db.Column(db.String(36), db.ForeignKey('medication_plans.id'), nullable=False)

    handelsname = db.Column(db.String(255), nullable=False)
    wirkstoff = db.Column(db.String(255))
    staerke = db.Column(db.String(100))
    darreichungsform = db.Column(db.String(100))
    pzn = db.Column(db.String(20))

    morgens = db.Column(db.String(50))
    mittags = db.Column(db.String(50))
    abends = db.Column(db.String(50))
    nachts = db.Column(db.String(50))
    bei_bedarf = db.Column(db.Boolean, default=False)
    bei_bedarf_max = db.Column(db.String(100))
    einnahmehinweis = db.Column(db.Text)

    is_btm = db.Column(db.Boolean, default=False)
    btm_nr = db.Column(db.String(100))
    btm_bestand = db.Column(db.Float, default=0)

    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class MedicationAdministration(db.Model):
    __tablename__ = 'medication_administrations'

    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    company_id = db.Column(db.String(36), db.ForeignKey('companies.id'), nullable=False)
    medication_id = db.Column(db.String(36), db.ForeignKey('medications.id'), nullable=False)
    patient_id = db.Column(db.String(36), db.ForeignKey('patients.id'), nullable=False)
    administered_by = db.Column(db.String(36), db.ForeignKey('employees.id'), nullable=False)
    verified_by = db.Column(db.String(36), db.ForeignKey('employees.id'))

    administered_at = db.Column(db.DateTime, default=datetime.utcnow)
    tatsaechliche_dosis = db.Column(db.String(100))
    einnahme_bestaetigt = db.Column(db.Boolean, default=False)
    ablehnung_grund = db.Column(db.Text)

    restmenge_vor = db.Column(db.Float)
    restmenge_nach = db.Column(db.Float)
    btm_versiegelung_ok = db.Column(db.Boolean)

    verification_method = db.Column(db.String(30), nullable=False, default='PIN_MAC_GPS')
    device_mac = db.Column(db.String(17))
    geo_lat = db.Column(db.Float)
    geo_lng = db.Column(db.Float)
    verifier_device_mac = db.Column(db.String(17))

    bemerkungen = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    medication = db.relationship('Medication', backref='administrations')
    administrator = db.relationship('Employee', foreign_keys=[administered_by])
    verifier = db.relationship('Employee', foreign_keys=[verified_by])


class BtmBuch(db.Model):
    __tablename__ = 'btm_buch'

    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    company_id = db.Column(db.String(36), db.ForeignKey('companies.id'), nullable=False)
    medication_id = db.Column(db.String(36), db.ForeignKey('medications.id'), nullable=False)

    buchungsdatum = db.Column(db.Date, nullable=False, default=date.today)
    buchungszeit = db.Column(db.Time, nullable=False)
    vorgang = db.Column(db.String(50), nullable=False)  # ZUGANG | ABGANG | BESTAND
    menge = db.Column(db.Float, nullable=False)
    einheit = db.Column(db.String(50))
    bestand_nach = db.Column(db.Float, nullable=False)

    patient_id = db.Column(db.String(36), db.ForeignKey('patients.id'))
    mitarbeiter_1_id = db.Column(db.String(36), db.ForeignKey('employees.id'), nullable=False)
    mitarbeiter_2_id = db.Column(db.String(36), db.ForeignKey('employees.id'), nullable=False)

    device_mac_1 = db.Column(db.String(17))
    device_mac_2 = db.Column(db.String(17))
    geo_lat = db.Column(db.Float)
    geo_lng = db.Column(db.Float)
    bemerkungen = db.Column(db.Text)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# ============================================================
# MEDICATION DOCUMENTS (Автоматически генерируемые документы медикаментов)
# ============================================================
class MedicationDocument(db.Model):
    __tablename__ = 'medication_documents'

    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    company_id = db.Column(db.String(36), db.ForeignKey('companies.id'), nullable=False)
    patient_id = db.Column(db.String(36), db.ForeignKey('patients.id'), nullable=False)
    medication_plan_id = db.Column(db.String(36), db.ForeignKey('medication_plans.id'), nullable=False)
    created_by = db.Column(db.String(36), db.ForeignKey('employees.id'), nullable=False)

    # Тип документа: MEDICATION_PLAN, MEDICATION_SCHEDULE, MEDICATION_REMINDER
    document_type = db.Column(db.String(50), nullable=False, default='MEDICATION_PLAN')

    # Заголовок и содержание
    title = db.Column(db.String(255), nullable=False)
    content = db.Column(db.Text, nullable=False)  # HTML content

    # Статус документа
    status = db.Column(db.String(50), nullable=False, default='ACTIVE')  # ACTIVE, ARCHIVED, SUPERSEDED

    # Когда документ стал невактуальным (если план обновлён)
    superseded_at = db.Column(db.DateTime)
    superseded_by = db.Column(db.String(36), db.ForeignKey('medication_documents.id'))

    # Временные метки
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Отношения
    patient = db.relationship('Patient', backref='medication_documents')
    medication_plan = db.relationship('MedicationPlan', backref='documents')
    creator = db.relationship('Employee', foreign_keys=[created_by])
    company = db.relationship('Company')

    __table_args__ = (
        db.Index('ix_medication_documents_patient_id', 'patient_id'),
        db.Index('ix_medication_documents_company_id', 'company_id'),
        db.Index('ix_medication_documents_status', 'status'),
        db.Index('ix_medication_documents_created_at', 'created_at'),
    )

    def __repr__(self):
        return f"<MedicationDocument {self.id} - {self.title}>"


# ============================================================
# LEISTUNGSNACHWEIS
# ============================================================
class Leistungskatalog(db.Model):
    __tablename__ = 'leistungskatalog'

    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    company_id = db.Column(db.String(36), db.ForeignKey('companies.id'), nullable=False)
    leistung_nr = db.Column(db.String(50))
    bezeichnung = db.Column(db.String(255), nullable=False)
    beschreibung = db.Column(db.Text)
    kategorie = db.Column(db.String(100))
    dauer_minuten = db.Column(db.Integer)
    preis = db.Column(db.Float)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Leistungsnachweis(db.Model):
    __tablename__ = 'leistungsnachweise'

    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    company_id = db.Column(db.String(36), db.ForeignKey('companies.id'), nullable=False)
    patient_id = db.Column(db.String(36), db.ForeignKey('patients.id'), nullable=False)
    employee_id = db.Column(db.String(36), db.ForeignKey('employees.id'), nullable=False)
    leistung_id = db.Column(db.String(36), db.ForeignKey('leistungskatalog.id'), nullable=False)

    durchgefuehrt_am = db.Column(db.Date, nullable=False, default=date.today)
    durchgefuehrt_um = db.Column(db.Time, nullable=False)
    dauer_minuten = db.Column(db.Integer)

    verification_method = db.Column(db.String(30), nullable=False, default='MAC_GPS')
    device_mac = db.Column(db.String(17))
    geo_lat = db.Column(db.Float)
    geo_lng = db.Column(db.Float)
    nfc_tag_id = db.Column(db.String(100))

    abgerechnet = db.Column(db.Boolean, default=False)
    bemerkungen = db.Column(db.Text)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    patient = db.relationship('Patient', backref='leistungsnachweise')
    employee = db.relationship('Employee', backref='leistungsnachweise')
    leistung = db.relationship('Leistungskatalog', backref='nachweise')


# ============================================================
# WUNDDOKUMENTATION
# ============================================================
class WoundDoc(db.Model):
    __tablename__ = 'wound_docs'

    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    company_id = db.Column(db.String(36), db.ForeignKey('companies.id'), nullable=False)
    patient_id = db.Column(db.String(36), db.ForeignKey('patients.id'), nullable=False)
    created_by = db.Column(db.String(36), db.ForeignKey('employees.id'), nullable=False)

    wunde_bezeichnung = db.Column(db.String(255), nullable=False)
    lokalisation = db.Column(db.String(255), nullable=False)
    stage = db.Column(db.String(50))
    erstfeststellung = db.Column(db.Date, nullable=False, default=date.today)
    ursache = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    patient = db.relationship('Patient', backref='wounds')
    assessments = db.relationship('WoundAssessment', backref='wound', lazy='dynamic')


class WoundAssessment(db.Model):
    __tablename__ = 'wound_assessments'

    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    wound_id = db.Column(db.String(36), db.ForeignKey('wound_docs.id'), nullable=False)
    assessed_by = db.Column(db.String(36), db.ForeignKey('employees.id'), nullable=False)

    assessment_date = db.Column(db.Date, nullable=False, default=date.today)
    assessment_time = db.Column(db.Time)

    groesse_laenge_cm = db.Column(db.Float)
    groesse_breite_cm = db.Column(db.Float)
    tiefe_cm = db.Column(db.Float)
    stage = db.Column(db.String(50))

    wundgrund = db.Column(db.Text)
    wundrand = db.Column(db.Text)
    exsudat_menge = db.Column(db.String(50))
    exsudat_art = db.Column(db.String(100))
    geruch = db.Column(db.String(50))

    foto_paths = db.Column(db.Text)  # JSON-строка с путями к файлам
    foto_ai_analysis = db.Column(db.Text)  # JSON-строка с анализом ИИ

    wundauflage = db.Column(db.String(255))
    wundspuelung = db.Column(db.String(255))
    verbandwechsel_interval = db.Column(db.String(100))
    bemerkungen = db.Column(db.Text)
    tendenz = db.Column(db.String(50))  # Verbesserung | Stagnation | Verschlechterung

    verification_method = db.Column(db.String(30), default='PIN_MAC_GPS')
    device_mac = db.Column(db.String(17))
    geo_lat = db.Column(db.Float)
    geo_lng = db.Column(db.Float)

    status = db.Column(db.String(20), default='COMPLETED')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    assessor = db.relationship('Employee', backref='wound_assessments')


# ============================================================
# STURZPROTOKOLL
# ============================================================
class Sturzprotokoll(db.Model):
    __tablename__ = 'sturzprotokolle'

    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    company_id = db.Column(db.String(36), db.ForeignKey('companies.id'), nullable=False)
    patient_id = db.Column(db.String(36), db.ForeignKey('patients.id'), nullable=False)
    reported_by = db.Column(db.String(36), db.ForeignKey('employees.id'), nullable=False)

    sturz_datum = db.Column(db.Date, nullable=False, default=date.today)
    sturz_uhrzeit = db.Column(db.Time)
    fundort = db.Column(db.String(255))
    sturzursache = db.Column(db.Text)
    verletzungen = db.Column(db.Text)
    massnahmen_sofort = db.Column(db.Text)
    arzt_informiert = db.Column(db.Boolean, default=False)
    arzt_informiert_um = db.Column(db.DateTime)
    angehoerige_informiert = db.Column(db.Boolean, default=False)
    severity = db.Column(db.String(20), default='MITTEL')

    device_mac = db.Column(db.String(17))
    geo_lat = db.Column(db.Float)
    geo_lng = db.Column(db.Float)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    patient = db.relationship('Patient', backref='sturzprotokolle')
    reporter = db.relationship('Employee', backref='sturzprotokolle')


# ============================================================
# AUDIT LOG
# ============================================================
class AuditLog(db.Model):
    __tablename__ = 'audit_log'

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    company_id = db.Column(db.String(36))
    user_id = db.Column(db.String(36))
    device_mac = db.Column(db.String(17))

    action = db.Column(db.String(100), nullable=False)
    entity_type = db.Column(db.String(100), nullable=False)
    entity_id = db.Column(db.String(36))

    old_values = db.Column(db.Text)
    new_values = db.Column(db.Text)

    ip_address = db.Column(db.String(45))
    geo_lat = db.Column(db.Float)
    geo_lng = db.Column(db.Float)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


# ============================================================
# SUBSCRIPTION PAYMENTS
# ============================================================
class SubscriptionPayment(db.Model):
    """Track monthly/annual subscription payments per company."""
    __tablename__ = 'subscription_payments'

    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    company_id = db.Column(db.String(36), db.ForeignKey('companies.id'), nullable=False)

    plan = db.Column(db.String(20), nullable=False)   # TRIAL | STARTER | PRO | PREMIUM
    betrag = db.Column(db.Numeric(10, 2), nullable=False)
    waehrung = db.Column(db.String(3), default='EUR')
    period_start = db.Column(db.Date, nullable=False)
    period_end = db.Column(db.Date, nullable=False)

    # PENDING | PAID | FAILED | REFUNDED
    status = db.Column(db.String(20), default='PENDING')
    payment_method = db.Column(db.String(50))   # STRIPE | BANK | INVOICE
    payment_ref = db.Column(db.String(255))     # Stripe charge id or bank reference
    stripe_invoice_id      = db.Column(db.String(100))   # in_xxx
    stripe_subscription_id = db.Column(db.String(100))   # sub_xxx (snapshot)
    rechnung_nr = db.Column(db.String(50))

    paid_at = db.Column(db.DateTime)
    notiz = db.Column(db.Text)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    company = db.relationship('Company', backref='payments')

    @property
    def betrag_display(self):
        return f'{self.betrag:.2f} {self.waehrung}'


# ============================================================
# PATIENT PHOTOS (Phase 3: Photo + GPS Capture)
# ============================================================
class PatientPhoto(db.Model):
    __tablename__ = 'patient_photos'

    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    company_id = db.Column(db.String(36), db.ForeignKey('companies.id'), nullable=False)
    patient_id = db.Column(db.String(36), db.ForeignKey('patients.id'), nullable=False)
    employee_id = db.Column(db.String(36), db.ForeignKey('employees.id'), nullable=False)

    # File path relative to UPLOAD_FOLDER
    file_path = db.Column(db.String(500), nullable=False)
    file_size = db.Column(db.Integer)
    mime_type = db.Column(db.String(50), default='image/jpeg')

    # GPS coordinates
    geo_lat = db.Column(db.Float)
    geo_lng = db.Column(db.Float)
    geo_accuracy = db.Column(db.Float)

    # Device information
    device_mac = db.Column(db.String(17))
    device_model = db.Column(db.String(255))

    # Photo metadata
    photo_type = db.Column(db.String(50), default='GENERAL')  # GENERAL, WOUND, PRESSURE_ULCER, INSPECTION
    description = db.Column(db.Text)
    tags = db.Column(db.String(500))

    # Verification
    verified_by = db.Column(db.String(36), db.ForeignKey('employees.id'))
    verified_at = db.Column(db.DateTime)

    # Lifecycle
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    patient = db.relationship('Patient', backref='photos', foreign_keys=[patient_id])
    employee = db.relationship('Employee', backref='patient_photos_uploaded', foreign_keys=[employee_id])
    verifier = db.relationship('Employee', backref='patient_photos_verified', foreign_keys=[verified_by])
    company = db.relationship('Company')

    __table_args__ = (
        db.Index('ix_patient_photos_company_id', 'company_id'),
        db.Index('ix_patient_photos_patient_id', 'patient_id'),
        db.Index('ix_patient_photos_employee_id', 'employee_id'),
        db.Index('ix_patient_photos_created_at', 'created_at'),
    )

    def __repr__(self):
        return f"<PatientPhoto {self.id} - {self.patient.full_name} by {self.employee.full_name}>"


# ============================================================
# EMPLOYEE LOCATION TRACKING (Phase 4: Real-time Route Tracking)
# ============================================================
class EmployeeLocation(db.Model):
    __tablename__ = 'employee_locations'

    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    company_id = db.Column(db.String(36), db.ForeignKey('companies.id'), nullable=False)
    employee_id = db.Column(db.String(36), db.ForeignKey('employees.id'), nullable=False)

    # GPS coordinates
    geo_lat = db.Column(db.Float, nullable=False)
    geo_lng = db.Column(db.Float, nullable=False)
    geo_accuracy = db.Column(db.Float)

    # Device information
    device_mac = db.Column(db.String(17))
    device_model = db.Column(db.String(255))

    # Movement data
    speed = db.Column(db.Float)  # m/s if available from GPS
    heading = db.Column(db.Float)  # degrees if available

    # Metadata
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    employee = db.relationship('Employee', backref='location_history')
    company = db.relationship('Company')

    __table_args__ = (
        db.Index('ix_employee_locations_company_id', 'company_id'),
        db.Index('ix_employee_locations_employee_id', 'employee_id'),
        db.Index('ix_employee_locations_created_at', 'created_at'),
        db.Index('ix_employee_locations_is_active', 'is_active'),
    )

    def __repr__(self):
        return f"<EmployeeLocation {self.employee.full_name} at {self.geo_lat}, {self.geo_lng}>"


# ============================================================
# PHASE 3.1: SCHEDULING & VISIT MANAGEMENT
# ============================================================
class Procedure(db.Model):
    """Справочник процедур ухода (создает администратор)"""
    __tablename__ = 'procedures'

    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    company_id = db.Column(db.String(36), db.ForeignKey('companies.id'), nullable=False)

    # Название и описание
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    category = db.Column(db.String(100))  # INJECTION, WOUND_CARE, MEASUREMENT, MEDICATION, etc.

    # Типичная длительность в минутах
    duration_minutes = db.Column(db.Integer, default=15)

    # Требуемая квалификация
    required_qualification = db.Column(db.String(100))  # PFLEGEFACHKRAFT, PFLEGEHILFSKRAFT, etc.

    # Требует ли двойной проверки (для лекарств/BTM)
    requires_verification = db.Column(db.Boolean, default=False)

    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    company = db.relationship('Company', backref='procedures')

    __table_args__ = (
        db.Index('ix_procedures_company_id', 'company_id'),
        db.Index('ix_procedures_is_active', 'is_active'),
    )

    def __repr__(self):
        return f"<Procedure {self.name}>"


class EmployeeSchedule(db.Model):
    """План работ для медсестры на день"""
    __tablename__ = 'employee_schedules'

    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    company_id = db.Column(db.String(36), db.ForeignKey('companies.id'), nullable=False)
    employee_id = db.Column(db.String(36), db.ForeignKey('employees.id'), nullable=False)
    patient_id = db.Column(db.String(36), db.ForeignKey('patients.id'), nullable=False)

    # Когда и где
    scheduled_date = db.Column(db.Date, nullable=False)
    scheduled_time = db.Column(db.Time, nullable=False)

    # Процедуры на этот визит (JSON array с IDs процедур)
    procedures = db.Column(db.Text)  # JSON: [{"id": "proc1", "name": "Injection"}]

    # Адрес (копия из пациента на момент создания плана)
    address_strasse = db.Column(db.String(255))
    address_hausnummer = db.Column(db.String(20))
    address_plz = db.Column(db.String(10))
    address_ort = db.Column(db.String(100))

    # GPS для оптимизации маршрута
    patient_geo_lat = db.Column(db.Float)
    patient_geo_lng = db.Column(db.Float)

    # Статус выполнения
    status = db.Column(db.String(20), default='PENDING')  # PENDING, IN_PROGRESS, COMPLETED, CANCELLED, RESCHEDULED

    # Заметки для медсестры
    notes = db.Column(db.Text)
    alerts = db.Column(db.Text)  # JSON: [{"type": "HIGH_RISK", "message": "Dekubitus!"}]

    # Отчет (связь с VisitReport после выполнения)
    visit_report_id = db.Column(db.String(36), db.ForeignKey('visit_reports.id'))

    # Дополнительно
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    employee = db.relationship('Employee', backref='schedules')
    patient = db.relationship('Patient', backref='schedules')
    company = db.relationship('Company', backref='employee_schedules')
    visit_report = db.relationship('VisitReport', foreign_keys=[visit_report_id], backref='schedule')

    __table_args__ = (
        db.Index('ix_employee_schedules_company_id', 'company_id'),
        db.Index('ix_employee_schedules_employee_id', 'employee_id'),
        db.Index('ix_employee_schedules_patient_id', 'patient_id'),
        db.Index('ix_employee_schedules_scheduled_date', 'scheduled_date'),
        db.Index('ix_employee_schedules_status', 'status'),
    )

    def __repr__(self):
        return f"<Schedule {self.employee.full_name} → {self.patient.full_name} on {self.scheduled_date}>"


class VisitReport(db.Model):
    """Отчет о выполнении визита (заполняет медсестра)"""
    __tablename__ = 'visit_reports'

    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    company_id = db.Column(db.String(36), db.ForeignKey('companies.id'), nullable=False)
    employee_id = db.Column(db.String(36), db.ForeignKey('employees.id'), nullable=False)
    patient_id = db.Column(db.String(36), db.ForeignKey('patients.id'), nullable=False)

    # Время визита
    visit_date = db.Column(db.Date, nullable=False)
    visit_start_time = db.Column(db.DateTime, nullable=False)
    visit_end_time = db.Column(db.DateTime)

    # Выполненные процедуры (JSON array)
    procedures_completed = db.Column(db.Text)  # JSON: [{"id": "proc1", "name": "Injection", "completed": true}]

    # Результаты и наблюдения
    observations = db.Column(db.Text)  # Свободный текст - что видела медсестра
    patient_condition = db.Column(db.String(100))  # STABLE, IMPROVED, DETERIORATED

    # Проблемы/Alerts
    issues_encountered = db.Column(db.Text)  # JSON array проблем

    # Фото (связь с PatientPhoto)
    photo_ids = db.Column(db.Text)  # JSON array PatientPhoto.id

    # Верификация действий
    verification_method = db.Column(db.String(30), default='MAC_GPS')
    device_mac = db.Column(db.String(17))
    geo_lat = db.Column(db.Float)
    geo_lng = db.Column(db.Float)

    # Подпись медсестры
    signature_confirmed = db.Column(db.Boolean, default=False)
    signature_time = db.Column(db.DateTime)

    # Верификация другой медсестрой/администратором
    verified_by = db.Column(db.String(36), db.ForeignKey('employees.id'))
    verified_at = db.Column(db.DateTime)
    verification_notes = db.Column(db.Text)

    # Статус
    status = db.Column(db.String(20), default='DRAFT')  # DRAFT, SUBMITTED, VERIFIED, LOCKED

    # Для отчетности/счетов
    billable_minutes = db.Column(db.Integer)  # Заполняется при верификации

    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    employee = db.relationship('Employee', backref='visit_reports', foreign_keys=[employee_id])
    patient = db.relationship('Patient', backref='visit_reports', foreign_keys=[patient_id])
    company = db.relationship('Company', backref='visit_reports')
    verifier = db.relationship('Employee', foreign_keys=[verified_by], backref='verified_reports')

    __table_args__ = (
        db.Index('ix_visit_reports_company_id', 'company_id'),
        db.Index('ix_visit_reports_employee_id', 'employee_id'),
        db.Index('ix_visit_reports_patient_id', 'patient_id'),
        db.Index('ix_visit_reports_visit_date', 'visit_date'),
        db.Index('ix_visit_reports_status', 'status'),
    )

    def __repr__(self):
        return f"<VisitReport {self.employee.full_name} → {self.patient.full_name} on {self.visit_date}>"


class ScheduleGeneration(db.Model):
    """История генерации планов AI (для аудита и отката)"""
    __tablename__ = 'schedule_generations'

    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    company_id = db.Column(db.String(36), db.ForeignKey('companies.id'), nullable=False)

    # Кто создал
    created_by = db.Column(db.String(36), db.ForeignKey('employees.id'), nullable=False)

    # Период генерации
    schedule_start_date = db.Column(db.Date, nullable=False)
    schedule_end_date = db.Column(db.Date, nullable=False)

    # AI Prompt что было отправлено (для аудита)
    ai_prompt = db.Column(db.Text)  # Деанонимизированные данные отправленные в Claude

    # AI Response (JSON)
    ai_response = db.Column(db.Text)  # JSON с предложенным планом

    # Статус генерации
    status = db.Column(db.String(20), default='GENERATED')  # GENERATED, APPROVED, DISTRIBUTED, CANCELLED

    # Одобрение
    approved_by = db.Column(db.String(36), db.ForeignKey('employees.id'))
    approved_at = db.Column(db.DateTime)
    approval_notes = db.Column(db.Text)

    # Распределение
    distributed_at = db.Column(db.DateTime)
    distributed_to_count = db.Column(db.Integer)  # Кому рассылается

    # Кол-во созданных schedules
    schedules_created = db.Column(db.Integer, default=0)

    # Деанонимизировать ли для AI
    anonymize_for_ai = db.Column(db.Boolean, default=True)

    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    company = db.relationship('Company', backref='schedule_generations')
    creator = db.relationship('Employee', foreign_keys=[created_by], backref='generated_schedules')
    approver = db.relationship('Employee', foreign_keys=[approved_by], backref='approved_schedules')

    __table_args__ = (
        db.Index('ix_schedule_generations_company_id', 'company_id'),
        db.Index('ix_schedule_generations_created_by', 'created_by'),
        db.Index('ix_schedule_generations_status', 'status'),
    )

    def __repr__(self):
        return f"<ScheduleGeneration {self.schedule_start_date} to {self.schedule_end_date}>"


# ============================================================
# PATIENT GREETINGS
# ============================================================
class PatientGreeting(db.Model):
    """KI-generierte Glückwünsche für Patienten (Geburtstag + religiöse Feiertage)."""
    __tablename__ = 'patient_greetings'

    id          = db.Column(db.Integer, primary_key=True, autoincrement=True)
    patient_id  = db.Column(db.String(36), db.ForeignKey('patients.id'), nullable=False)
    company_id  = db.Column(db.String(36), db.ForeignKey('companies.id'), nullable=False)

    # Anlass
    occasion      = db.Column(db.String(200), nullable=False)   # z.B. "Ostersonntag", "Geburtstag (83. Geburtstag)"
    occasion_type = db.Column(db.String(50),  nullable=False)   # 'birthday' | 'religious' | 'national'

    # KI-generierter Text
    message = db.Column(db.Text, nullable=False)

    # E-Mail-Status
    sent_email = db.Column(db.Boolean, default=False)
    sent_at    = db.Column(db.DateTime)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    patient = db.relationship('Patient', backref=db.backref('greetings', lazy='dynamic'))
    company = db.relationship('Company', backref='greetings')

    __table_args__ = (
        db.Index('ix_patient_greetings_patient_id', 'patient_id'),
        db.Index('ix_patient_greetings_company_id', 'company_id'),
        db.Index('ix_patient_greetings_created_at', 'created_at'),
    )

    @property
    def occasion_icon(self):
        icons = {
            'birthday':  '🎂',
            'religious': '🙏',
            'national':  '🎉',
        }
        return icons.get(self.occasion_type, '🌸')

    def __repr__(self):
        return f"<PatientGreeting {self.patient_id} – {self.occasion}>"


# ============================================================
# FUHRPARK
# ============================================================

class Fahrzeug(db.Model):
    """Fahrzeugkartei — jedes Fahrzeug des Pflegedienstes."""
    __tablename__ = 'fahrzeuge'

    id         = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    company_id = db.Column(db.String(36), db.ForeignKey('companies.id'), nullable=False)

    kennzeichen            = db.Column(db.String(20),  nullable=False)   # z.B. "B-PF 1234"
    marke                  = db.Column(db.String(50))                    # VW, Citroën …
    modell                 = db.Column(db.String(100))                   # Caddy, Berlingo …
    baujahr                = db.Column(db.Integer)
    farbe                  = db.Column(db.String(30))
    kraftstoff             = db.Column(db.String(20), default='Diesel')  # Benzin/Diesel/Elektro/Hybrid
    fahrgestellnummer      = db.Column(db.String(50))

    tuev_bis               = db.Column(db.Date)    # HU / TÜV-Ablauf
    versicherung_bis       = db.Column(db.Date)    # Versicherungsablauf
    versicherung_nr        = db.Column(db.String(50))
    versicherung_gesellschaft = db.Column(db.String(100))

    km_stand               = db.Column(db.Integer)   # aktueller Kilometerstand
    km_stand_datum         = db.Column(db.Date)      # wann abgelesen

    anschaffungsdatum      = db.Column(db.Date)

    # AKTIV | WERKSTATT | AUSSER_BETRIEB
    status    = db.Column(db.String(20), default='AKTIV')
    notizen   = db.Column(db.Text)

    deleted_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    company = db.relationship('Company', backref='fahrzeuge')

    __table_args__ = (
        db.Index('ix_fahrzeuge_company_id', 'company_id'),
        db.Index('ix_fahrzeuge_status', 'status'),
    )

    # ── Hilfseigenschaften ────────────────────────────────────
    @property
    def tuev_tage(self):
        if not self.tuev_bis:
            return None
        return (self.tuev_bis - date.today()).days

    @property
    def versicherung_tage(self):
        if not self.versicherung_bis:
            return None
        return (self.versicherung_bis - date.today()).days

    def _doc_status(self, tage):
        if tage is None:  return 'unknown'
        if tage < 0:      return 'expired'
        if tage <= 14:    return 'critical'
        if tage <= 30:    return 'warning'
        return 'ok'

    @property
    def tuev_status(self):
        return self._doc_status(self.tuev_tage)

    @property
    def versicherung_status(self):
        return self._doc_status(self.versicherung_tage)

    @property
    def hat_alerts(self):
        return self.tuev_status in ('expired', 'critical', 'warning') or \
               self.versicherung_status in ('expired', 'critical', 'warning')

    @property
    def display_name(self):
        parts = [p for p in [self.marke, self.modell, self.kennzeichen] if p]
        return ' · '.join(parts) if parts else self.kennzeichen

    def __repr__(self):
        return f"<Fahrzeug {self.kennzeichen}>"


class Kilometerbuch(db.Model):
    """Fahrtenbucheintrag — jede Tour eines Fahrers."""
    __tablename__ = 'kilometerbuch'

    id          = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    company_id  = db.Column(db.String(36), db.ForeignKey('companies.id'), nullable=False)
    fahrzeug_id = db.Column(db.String(36), db.ForeignKey('fahrzeuge.id'), nullable=False)
    employee_id = db.Column(db.String(36), db.ForeignKey('employees.id'), nullable=False)
    patient_id  = db.Column(db.String(36), db.ForeignKey('patients.id'))  # optional

    datum       = db.Column(db.Date, nullable=False, default=date.today)
    km_start    = db.Column(db.Integer, nullable=False)
    km_end      = db.Column(db.Integer, nullable=False)

    abfahrt_ort = db.Column(db.String(200))
    ziel_ort    = db.Column(db.String(200))
    # PATIENTENBESUCH | BESORGUNG | WERKSTATT | SONSTIGES
    zweck       = db.Column(db.String(30), default='PATIENTENBESUCH')

    kraftstoff_kosten = db.Column(db.Numeric(8, 2))
    kraftstoff_liter  = db.Column(db.Numeric(6, 2))
    bemerkungen       = db.Column(db.Text)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    fahrzeug = db.relationship('Fahrzeug', backref=db.backref('fahrten', lazy='dynamic'))
    fahrer   = db.relationship('Employee', backref='fahrten')
    patient  = db.relationship('Patient',  backref='fahrten')

    __table_args__ = (
        db.Index('ix_kilometerbuch_fahrzeug_id', 'fahrzeug_id'),
        db.Index('ix_kilometerbuch_employee_id', 'employee_id'),
        db.Index('ix_kilometerbuch_datum',       'datum'),
    )

    @property
    def km_gesamt(self):
        return max(0, (self.km_end or 0) - (self.km_start or 0))

    def __repr__(self):
        return f"<Kilometerbuch {self.datum} {self.km_gesamt}km>"


class Schadensmeldung(db.Model):
    """Schadensmeldung für ein Fahrzeug."""
    __tablename__ = 'schadensmeldungen'

    id          = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    company_id  = db.Column(db.String(36), db.ForeignKey('companies.id'), nullable=False)
    fahrzeug_id = db.Column(db.String(36), db.ForeignKey('fahrzeuge.id'), nullable=False)
    employee_id = db.Column(db.String(36), db.ForeignKey('employees.id'), nullable=False)

    datum       = db.Column(db.Date, nullable=False, default=date.today)
    beschreibung = db.Column(db.Text, nullable=False)
    ort         = db.Column(db.String(200))

    versicherung_gemeldet = db.Column(db.Boolean, default=False)
    reparatur_kosten      = db.Column(db.Numeric(10, 2))

    # OFFEN | IN_REPARATUR | ERLEDIGT
    status     = db.Column(db.String(20), default='OFFEN')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    fahrzeug = db.relationship('Fahrzeug', backref=db.backref('schaeden', lazy='dynamic'))
    melder   = db.relationship('Employee', backref='schadensmeldungen')

    __table_args__ = (
        db.Index('ix_schadensmeldungen_fahrzeug_id', 'fahrzeug_id'),
    )

    def __repr__(self):
        return f"<Schadensmeldung {self.fahrzeug_id} {self.datum}>"


class Wartungseintrag(db.Model):
    """Wartungs- und Serviceprotokoll für ein Fahrzeug."""
    __tablename__ = 'wartungsprotokoll'

    id          = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    company_id  = db.Column(db.String(36), db.ForeignKey('companies.id'), nullable=False)
    fahrzeug_id = db.Column(db.String(36), db.ForeignKey('fahrzeuge.id'), nullable=False)
    employee_id = db.Column(db.String(36), db.ForeignKey('employees.id'))  # wer eingetragen hat

    datum       = db.Column(db.Date, nullable=False, default=date.today)
    # OELWECHSEL | REIFEN | BREMSEN | INSPEKTION | HU_VORBEREITUNG | KLIMAANLAGE | SONSTIGES
    art         = db.Column(db.String(30), nullable=False)
    beschreibung = db.Column(db.Text)
    werkstatt   = db.Column(db.String(200))
    km_stand    = db.Column(db.Integer)
    kosten      = db.Column(db.Numeric(10, 2))

    # Nächste Fälligkeit
    naechster_termin = db.Column(db.Date)
    naechste_km      = db.Column(db.Integer)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    fahrzeug  = db.relationship('Fahrzeug',  backref=db.backref('wartungen',  lazy='dynamic'))
    erfasser  = db.relationship('Employee',  backref='wartungseintraege')

    __table_args__ = (
        db.Index('ix_wartungsprotokoll_fahrzeug_id', 'fahrzeug_id'),
        db.Index('ix_wartungsprotokoll_datum',       'datum'),
    )

    ART_LABELS = {
        'OELWECHSEL':      '🔧 Ölwechsel',
        'REIFEN':          '🔄 Reifenwechsel',
        'BREMSEN':         '🛑 Bremsen',
        'INSPEKTION':      '🔍 Inspektion',
        'HU_VORBEREITUNG': '📋 HU-Vorbereitung',
        'KLIMAANLAGE':     '❄️ Klimaanlage',
        'SONSTIGES':       '📝 Sonstiges',
    }

    @property
    def art_label(self):
        return self.ART_LABELS.get(self.art, self.art)

    @property
    def faellig_tage(self):
        if not self.naechster_termin:
            return None
        return (self.naechster_termin - date.today()).days

    @property
    def faellig_status(self):
        t = self.faellig_tage
        if t is None:  return 'unknown'
        if t < 0:      return 'expired'
        if t <= 14:    return 'critical'
        if t <= 30:    return 'warning'
        return 'ok'

    def __repr__(self):
        return f"<Wartungseintrag {self.fahrzeug_id} {self.art} {self.datum}>"


# ============================================================
# BUCHHALTUNG
# ============================================================

class KassenbuchEintrag(db.Model):
    """Einnahmen/Ausgaben-Kassenbuch für den Pflegedienst."""
    __tablename__ = 'kassenbuch'

    id          = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    company_id  = db.Column(db.String(36), db.ForeignKey('companies.id'), nullable=False)
    employee_id = db.Column(db.String(36), db.ForeignKey('employees.id'))  # erstellt von
    patient_id  = db.Column(db.String(36), db.ForeignKey('patients.id'))   # optional

    datum       = db.Column(db.Date, nullable=False, default=date.today)
    # EINNAHME | AUSGABE
    art         = db.Column(db.String(10), nullable=False)
    kategorie   = db.Column(db.String(50), nullable=False)
    betrag      = db.Column(db.Numeric(10, 2), nullable=False)
    beschreibung = db.Column(db.String(500))
    beleg_nr    = db.Column(db.String(100))   # Belegnummer / Rechnungsnummer

    # Nur für Einnahmen: welche Leistungsnachweise sind damit abgedeckt (JSON-Array IDs)
    leistungs_ids = db.Column(db.Text)

    created_at  = db.Column(db.DateTime, default=datetime.utcnow)
    deleted_at  = db.Column(db.DateTime)

    ersteller = db.relationship('Employee', backref='kassenbuch_eintraege')
    patient   = db.relationship('Patient',  backref='kassenbuch_eintraege')

    __table_args__ = (
        db.Index('ix_kassenbuch_company_id', 'company_id'),
        db.Index('ix_kassenbuch_datum',      'datum'),
        db.Index('ix_kassenbuch_art',        'art'),
    )

    # ── Kategorien-Definitionen ──────────────────────────────
    EINNAHMEN_KATEGORIEN = {
        'PFLEGEKASSE':     '🏛️ Pflegekasse',
        'PRIVATPATIENT':   '👤 Privatpatient',
        'EIGENANTEIL':     '💶 Eigenanteil Patient',
        'FOERDERUNG':      '📋 Förderung / Zuschuss',
        'SONSTIGE_EINNAHME': '➕ Sonstige Einnahme',
    }
    AUSGABEN_KATEGORIEN = {
        'KRAFTSTOFF':      '⛽ Kraftstoff',
        'FAHRZEUG_WARTUNG':'🔧 Fahrzeugwartung/-reparatur',
        'GEHAELTER':       '👥 Gehälter / Löhne',
        'MIETE':           '🏢 Miete / Leasing',
        'MATERIAL_PFLEGE': '🩺 Pflegematerial',
        'BUERO':           '📎 Bürobedarf',
        'VERSICHERUNG':    '🛡️ Versicherung',
        'STEUER':          '🧾 Steuer / Abgaben',
        'FORTBILDUNG':     '📚 Fortbildung',
        'SONSTIGE_AUSGABE':'➖ Sonstige Ausgabe',
    }

    @property
    def kategorie_label(self):
        alle = {**self.EINNAHMEN_KATEGORIEN, **self.AUSGABEN_KATEGORIEN}
        return alle.get(self.kategorie, self.kategorie)

    @property
    def ist_einnahme(self):
        return self.art == 'EINNAHME'

    @property
    def betrag_vorzeichenbehaftet(self):
        """Positiv für Einnahmen, negativ für Ausgaben (für Saldo-Berechnung)."""
        b = float(self.betrag)
        return b if self.ist_einnahme else -b

    def __repr__(self):
        return f"<KassenbuchEintrag {self.datum} {self.art} {self.betrag}>"


# ============================================================
# SCHICHTPLANUNG (Dienstplan)
# ============================================================
class Dienstschicht(db.Model):
    """Ein Schichteintrag für einen Mitarbeiter an einem Tag."""
    __tablename__ = 'dienstschichten'

    id         = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    company_id = db.Column(db.String(36), db.ForeignKey('companies.id'), nullable=False)
    employee_id = db.Column(db.String(36), db.ForeignKey('employees.id'), nullable=False)

    datum      = db.Column(db.Date, nullable=False)
    # FRUEH | SPAET | NACHT | FREI | URLAUB | KRANK | FORTBILDUNG | SONSTIGES
    schicht_typ = db.Column(db.String(20), nullable=False, default='FRUEH')

    beginn     = db.Column(db.Time)
    ende       = db.Column(db.Time)
    bereich    = db.Column(db.String(100))
    notiz      = db.Column(db.String(500))

    created_by = db.Column(db.String(36), db.ForeignKey('employees.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    employee   = db.relationship('Employee', foreign_keys=[employee_id], backref='schichten')
    ersteller  = db.relationship('Employee', foreign_keys=[created_by])
    company    = db.relationship('Company',  backref='schichten')

    __table_args__ = (
        db.UniqueConstraint('company_id', 'employee_id', 'datum',
                            name='uq_dienstschicht_employee_datum'),
        db.Index('ix_dienstschichten_company_id', 'company_id'),
        db.Index('ix_dienstschichten_employee_id', 'employee_id'),
        db.Index('ix_dienstschichten_datum', 'datum'),
    )

    # (label, Bootstrap-Farbe, Kürzel, default_beginn, default_ende)
    TYPEN = {
        'FRUEH':       ('Frühschicht',  'success',   'F',  '06:00', '14:00'),
        'SPAET':       ('Spätschicht',  'primary',   'S',  '14:00', '22:00'),
        'NACHT':       ('Nachtschicht', 'dark',      'N',  '22:00', '06:00'),
        'FREI':        ('Frei',         'secondary', '—',  None,    None),
        'URLAUB':      ('Urlaub',       'info',      'U',  None,    None),
        'KRANK':       ('Krank',        'danger',    'K',  None,    None),
        'FORTBILDUNG': ('Fortbildung',  'warning',   'FB', None,    None),
        'SONSTIGES':   ('Sonstiges',    'light',     '?',  None,    None),
    }

    @property
    def typ_label(self):
        return self.TYPEN.get(self.schicht_typ, (self.schicht_typ,))[0]

    @property
    def typ_farbe(self):
        return self.TYPEN.get(self.schicht_typ, ('', 'secondary'))[1]

    @property
    def typ_kuerzel(self):
        return self.TYPEN.get(self.schicht_typ, ('', '', '?'))[2]

    @property
    def ist_arbeitstag(self):
        return self.schicht_typ in ('FRUEH', 'SPAET', 'NACHT', 'SONSTIGES')

    def __repr__(self):
        return f"<Dienstschicht {self.employee_id} {self.datum} {self.schicht_typ}>"
