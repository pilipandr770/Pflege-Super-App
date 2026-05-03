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

    # Auth
    password_hash = db.Column(db.Text)
    pin_hash = db.Column(db.Text)
    last_login_at = db.Column(db.DateTime)

    # Разрешения
    can_administer_btm = db.Column(db.Boolean, default=False)
    can_wound_care = db.Column(db.Boolean, default=False)
    can_approve_documents = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)

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
        return self.role == 'ADMIN'

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

    # Контакты
    betreuer_name = db.Column(db.String(255))
    betreuer_telefon = db.Column(db.String(50))
    betreuer_verhaeltnis = db.Column(db.String(100))
    hausarzt_name = db.Column(db.String(255))
    hausarzt_telefon = db.Column(db.String(50))

    # Pflege
    pflegegrad = db.Column(db.String(1))
    pflegegrad_seit = db.Column(db.Date)
    zimmer_nr = db.Column(db.String(20))
    bett_nr = db.Column(db.String(20))
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
    created_by = db.Column(db.String(36), db.ForeignKey('employees.id'), nullable=False)
    prescribed_by = db.Column(db.String(255))

    valid_from = db.Column(db.Date, nullable=False, default=date.today)
    valid_until = db.Column(db.Date)
    is_current = db.Column(db.Boolean, default=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    patient = db.relationship('Patient', backref='medication_plans')
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
