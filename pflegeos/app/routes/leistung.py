from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app.extensions import db
from app.models import Leistungsnachweis, Leistungskatalog, Patient
from app.utils.auth import log_action
from datetime import datetime, date, time as dtime

leistung_bp = Blueprint('leistung', __name__)

# ─────────────────────────────────────────────────────────────
# Vollständiger SGB XI / SGB V Leistungskatalog (LK-System)
# Grundlage: Leistungskomplex-Vergütungsvereinbarungen der
# Pflegekassen — gültig für ambulante Pflegedienste in Deutschland
# ─────────────────────────────────────────────────────────────
STANDARD_KATALOG = [
    # ── Körperpflege ──────────────────────────────────────────
    dict(leistung_nr='LK01', bezeichnung='Kleine Körperpflege (Teilwäsche)',
         beschreibung='Waschen von Gesicht, Händen, Intimbereiche; Mund-/Zahnpflege, Kämmen',
         kategorie='Körperpflege', dauer_minuten=20, preis=7.49),
    dict(leistung_nr='LK02', bezeichnung='Große Körperpflege (Ganzkörperwäsche im Bett)',
         beschreibung='Vollständige Körperpflege im Bett inkl. Hautpflege, Kämmen, Rasieren',
         kategorie='Körperpflege', dauer_minuten=35, preis=13.70),
    dict(leistung_nr='LK03', bezeichnung='Duschen / Baden (inkl. An-/Auskleiden)',
         beschreibung='Vollbad oder Dusche inkl. An-/Auskleiden, Hautpflege, Haarpflege',
         kategorie='Körperpflege', dauer_minuten=45, preis=18.12),
    dict(leistung_nr='LK04', bezeichnung='Mund-, Zahn- und Prothesenpflege',
         beschreibung='Zähneputzen, Prothesenreinigung, Mundspülung',
         kategorie='Körperpflege', dauer_minuten=10, preis=3.85),
    dict(leistung_nr='LK05', bezeichnung='Kämmen / Rasieren / Nagelpflege',
         beschreibung='Haare kämmen/bürsten, Rasieren, Fingernägel feilen (nicht medizinisch)',
         kategorie='Körperpflege', dauer_minuten=10, preis=3.50),
    dict(leistung_nr='LK06', bezeichnung='An- und Auskleiden',
         beschreibung='Hilfe beim An- und Ausziehen der Kleidung, inkl. Strümpfe',
         kategorie='Körperpflege', dauer_minuten=15, preis=5.71),

    # ── Ernährung ─────────────────────────────────────────────
    dict(leistung_nr='LK07', bezeichnung='Mundgerechte Zubereitung der Mahlzeit',
         beschreibung='Schneiden, Portionieren, Servieren — kein Kochen',
         kategorie='Ernährung', dauer_minuten=10, preis=3.50),
    dict(leistung_nr='LK08', bezeichnung='Hilfe bei der Nahrungsaufnahme',
         beschreibung='Unterstützung / vollständige Übernahme bei Essen und Trinken',
         kategorie='Ernährung', dauer_minuten=20, preis=6.54),
    dict(leistung_nr='LK09', bezeichnung='Sondenkost anlegen und verabreichen',
         beschreibung='Enterale Ernährung über PEG/Nasensonde, Kontrolle der Sonde',
         kategorie='Ernährung', dauer_minuten=15, preis=5.90),

    # ── Mobilität ─────────────────────────────────────────────
    dict(leistung_nr='LK10', bezeichnung='Hilfe beim Aufstehen / Zubettgehen',
         beschreibung='Aufstehen aus dem Bett, Hinlegen, Sicherung beim Transfer',
         kategorie='Mobilität', dauer_minuten=15, preis=5.71),
    dict(leistung_nr='LK11', bezeichnung='Lagern / Positionswechsel (Dekubitusprophylaxe)',
         beschreibung='Regelmäßige Umlagerung zur Druckentlastung, Lagerungshilfen',
         kategorie='Mobilität', dauer_minuten=20, preis=7.49),
    dict(leistung_nr='LK12', bezeichnung='Transfer (Rollstuhl / Gehilfe / Lifter)',
         beschreibung='Umsetzen vom Bett in Rollstuhl und zurück, Begleitung beim Gehen',
         kategorie='Mobilität', dauer_minuten=10, preis=3.85),

    # ── Hauswirtschaft ────────────────────────────────────────
    dict(leistung_nr='LK14', bezeichnung='Reinigung des Wohnbereichs',
         beschreibung='Staubsaugen, Wischen, Abstauben des Wohn-/Schlafzimmers',
         kategorie='Hauswirtschaft', dauer_minuten=45, preis=16.68),
    dict(leistung_nr='LK15', bezeichnung='Reinigung Sanitärbereich (WC/Bad)',
         beschreibung='Reinigung von Badezimmer, Toilette, Waschbecken',
         kategorie='Hauswirtschaft', dauer_minuten=30, preis=11.12),
    dict(leistung_nr='LK16', bezeichnung='Wäschepflege / Waschen und Wechseln',
         beschreibung='Wäsche sortieren, waschen, trocknen, zusammenlegen',
         kategorie='Hauswirtschaft', dauer_minuten=30, preis=11.12),
    dict(leistung_nr='LK17', bezeichnung='Einkaufen',
         beschreibung='Besorgungen für den täglichen Bedarf (Lebensmittel, Drogerie)',
         kategorie='Hauswirtschaft', dauer_minuten=45, preis=16.68),
    dict(leistung_nr='LK18', bezeichnung='Kochen einer Hauptmahlzeit',
         beschreibung='Zubereitung von Mittagessen oder Abendessen inkl. Abwasch',
         kategorie='Hauswirtschaft', dauer_minuten=30, preis=11.12),

    # ── Behandlungspflege (SGB V § 37) ───────────────────────
    dict(leistung_nr='LK20', bezeichnung='Medikamentengabe oral / sublingual',
         beschreibung='Richten und Verabreichen von Tabletten, Tropfen, Suppositorien',
         kategorie='Behandlungspflege', dauer_minuten=10, preis=3.85),
    dict(leistung_nr='LK21', bezeichnung='Injektion subkutan (z.B. Insulin)',
         beschreibung='Subcutane Injektion inkl. Blutzuckermessung bei Bedarf',
         kategorie='Behandlungspflege', dauer_minuten=10, preis=5.20),
    dict(leistung_nr='LK22', bezeichnung='Injektion intramuskulär',
         beschreibung='Intramuskuläre Injektion nach ärztlicher Verordnung',
         kategorie='Behandlungspflege', dauer_minuten=15, preis=6.80),
    dict(leistung_nr='LK23', bezeichnung='Verbandwechsel einfach',
         beschreibung='Steriler Verbandwechsel bei einfachen Wunden, Nähten, Schürfwunden',
         kategorie='Behandlungspflege', dauer_minuten=20, preis=8.50),
    dict(leistung_nr='LK24', bezeichnung='Wundversorgung komplex (Dekubitus / chronische Wunde)',
         beschreibung='Spezialisierte Wundversorgung bei Dekubitus, Ulcus cruris, diabetischem Fuß',
         kategorie='Behandlungspflege', dauer_minuten=45, preis=19.80),
    dict(leistung_nr='LK25', bezeichnung='Blutdruckmessung',
         beschreibung='Blutdruckkontrolle, Dokumentation, Weiterleitung an Arzt bei Abweichung',
         kategorie='Behandlungspflege', dauer_minuten=10, preis=3.50),
    dict(leistung_nr='LK26', bezeichnung='Blutzuckermessung',
         beschreibung='Kapilläre Blutzuckermessung, Dokumentation, ggf. Insulin-Anpassung',
         kategorie='Behandlungspflege', dauer_minuten=5, preis=3.20),
    dict(leistung_nr='LK27', bezeichnung='Harnkatheter-Versorgung (liegend / suprapubisch)',
         beschreibung='Pflege, Kontrolle und Wechsel des Dauerkatheters nach ärztl. Verordnung',
         kategorie='Behandlungspflege', dauer_minuten=20, preis=9.10),
    dict(leistung_nr='LK28', bezeichnung='Kompressionsstrümpfe an-/ausziehen',
         beschreibung='An- und Ausziehen medizinischer Kompressionsstrümpfe Kl. I–III',
         kategorie='Behandlungspflege', dauer_minuten=15, preis=5.90),
    dict(leistung_nr='LK29', bezeichnung='Inhalationstherapie',
         beschreibung='Inhalation mit Vernebler/Spacer, Atemübungen nach Verordnung',
         kategorie='Behandlungspflege', dauer_minuten=15, preis=5.90),
    dict(leistung_nr='LK30', bezeichnung='Stoma-Versorgung (Kolostomie / Urostomie)',
         beschreibung='Versorgung und Wechsel des Stomabeutels, Stomarandpflege',
         kategorie='Behandlungspflege', dauer_minuten=30, preis=14.50),

    # ── Soziale Betreuung (§ 45b SGB XI) ─────────────────────
    dict(leistung_nr='LK31', bezeichnung='Betreuungsleistungen / Alltagsbegleitung',
         beschreibung='Gespräch, Vorlesen, Spaziergang, Beschäftigung — nach § 45b SGB XI',
         kategorie='Soziale Betreuung', dauer_minuten=60, preis=25.20),
    dict(leistung_nr='LK32', bezeichnung='Kognitive Aktivierung / Gedächtnistraining',
         beschreibung='Gedächtnisübungen, Wahrnehmungsförderung, Orientierungshilfe',
         kategorie='Soziale Betreuung', dauer_minuten=45, preis=18.70),
    dict(leistung_nr='LK33', bezeichnung='Nachtbereitschaft / Nachtpflege',
         beschreibung='Betreuung und Pflege in der Nacht (pro Einsatz)',
         kategorie='Soziale Betreuung', dauer_minuten=60, preis=32.50),

    # ── Beratung ──────────────────────────────────────────────
    dict(leistung_nr='LK34', bezeichnung='Pflegeberatungsbesuch (§ 37 Abs. 3 SGB XI)',
         beschreibung='Qualitätssichernder Beratungsbesuch für Pflegegeldempfänger',
         kategorie='Beratung', dauer_minuten=30, preis=23.50),
    dict(leistung_nr='LK35', bezeichnung='Erstgespräch / Pflegeanamnese',
         beschreibung='Aufnahme der Pflegeanamnese, Erhebung des Hilfebedarfs, SIS-Vorbereitung',
         kategorie='Beratung', dauer_minuten=60, preis=38.00),
]


def seed_leistungskatalog(company_id):
    """Erstellt den Standard-SGB XI Leistungskatalog für eine neue Firma."""
    for item in STANDARD_KATALOG:
        eintrag = Leistungskatalog(
            company_id=company_id,
            leistung_nr=item['leistung_nr'],
            bezeichnung=item['bezeichnung'],
            beschreibung=item.get('beschreibung', ''),
            kategorie=item.get('kategorie', ''),
            dauer_minuten=item.get('dauer_minuten'),
            preis=item.get('preis'),
            is_active=True,
        )
        db.session.add(eintrag)
    db.session.commit()


@leistung_bp.route('/patient/<patient_id>')
@login_required
def patient_list(patient_id):
    p = _get_patient(patient_id)
    month = request.args.get('month', date.today().strftime('%Y-%m'))
    try:
        year, mon = map(int, month.split('-'))
        from calendar import monthrange
        days = monthrange(year, mon)[1]
        start = date(year, mon, 1)
        end = date(year, mon, days)
    except Exception:
        start = end = date.today()

    nachweise = Leistungsnachweis.query.filter(
        Leistungsnachweis.patient_id == patient_id,
        Leistungsnachweis.durchgefuehrt_am >= start,
        Leistungsnachweis.durchgefuehrt_am <= end,
    ).order_by(Leistungsnachweis.durchgefuehrt_am.desc(),
               Leistungsnachweis.durchgefuehrt_um.desc()).all()

    return render_template('leistung/list.html', patient=p,
                           nachweise=nachweise, month=month)


@leistung_bp.route('/new', methods=['GET', 'POST'])
@login_required
def new():
    patient_id = request.args.get('patient_id') or request.form.get('patient_id')
    p = _get_patient(patient_id) if patient_id else None

    katalog = Leistungskatalog.query.filter_by(
        company_id=current_user.company_id, is_active=True
    ).order_by(Leistungskatalog.kategorie, Leistungskatalog.bezeichnung).all()

    if request.method == 'POST':
        fd = request.form
        leistung_id = fd.get('leistung_id')
        if not leistung_id or not patient_id:
            flash('Bitte Patient und Leistung auswählen.', 'danger')
            return redirect(request.url)

        nachweis = Leistungsnachweis(
            company_id=current_user.company_id,
            patient_id=patient_id,
            employee_id=current_user.id,
            leistung_id=leistung_id,
            durchgefuehrt_am=_parse_date(fd.get('datum')) or date.today(),
            durchgefuehrt_um=_parse_time(fd.get('uhrzeit')) or datetime.utcnow().time(),
            dauer_minuten=int(fd['dauer']) if fd.get('dauer') else None,
            verification_method=fd.get('verification_method', 'MAC_GPS'),
            device_mac=fd.get('device_mac', '').strip() or None,
            geo_lat=_float(fd.get('geo_lat')),
            geo_lng=_float(fd.get('geo_lng')),
            nfc_tag_id=fd.get('nfc_tag_id', '').strip() or None,
            bemerkungen=fd.get('bemerkungen', '').strip(),
        )
        db.session.add(nachweis)
        db.session.flush()  # nachweis.id ist jetzt verfügbar

        # Fotos verknüpfen: photo_ids aus dem Formular lesen und Tags aktualisieren
        import json as _json
        try:
            photo_ids = _json.loads(fd.get('photo_ids', '[]'))
        except Exception:
            photo_ids = []

        if photo_ids:
            from app.models import PatientPhoto
            for pid in photo_ids:
                photo = PatientPhoto.query.filter_by(
                    id=pid, company_id=current_user.company_id
                ).first()
                if photo:
                    # Ersetze 'leistung:pending' durch 'nachweis:<id>'
                    existing = [t for t in (photo.tags or '').split(',') if t and not t.startswith('leistung:')]
                    existing.append(f'nachweis:{nachweis.id}')
                    photo.tags = ','.join(existing)

        db.session.commit()
        log_action('CREATE', 'leistungsnachweise', entity_id=nachweis.id)
        flash('Leistung dokumentiert.', 'success')
        return redirect(url_for('leistung.patient_list', patient_id=patient_id))

    patients = Patient.query.filter_by(
        company_id=current_user.company_id, status='AKTIV', deleted_at=None
    ).order_by(Patient.nachname).all()

    return render_template('leistung/form.html',
                           patient=p, patients=patients,
                           katalog=katalog, today=date.today())


@leistung_bp.route('/katalog', methods=['GET', 'POST'])
@login_required
def katalog_manage():
    if not current_user.is_admin:
        flash('Keine Berechtigung.', 'danger')
        return redirect(url_for('dashboard.index'))

    if request.method == 'POST':
        fd = request.form
        bezeichnung = fd.get('bezeichnung', '').strip()
        if not bezeichnung:
            flash('Bezeichnung ist ein Pflichtfeld.', 'danger')
            return redirect(request.url)
        item = Leistungskatalog(
            company_id=current_user.company_id,
            leistung_nr=fd.get('leistung_nr', '').strip(),
            bezeichnung=bezeichnung,
            beschreibung=fd.get('beschreibung', '').strip(),
            kategorie=fd.get('kategorie', '').strip(),
            dauer_minuten=int(fd['dauer_minuten']) if fd.get('dauer_minuten') else None,
            preis=float(fd['preis']) if fd.get('preis') else None,
        )
        db.session.add(item)
        db.session.commit()
        flash('Leistung hinzugefügt.', 'success')
        return redirect(url_for('leistung.katalog_manage'))

    items = Leistungskatalog.query.filter_by(
        company_id=current_user.company_id
    ).order_by(Leistungskatalog.kategorie, Leistungskatalog.leistung_nr).all()

    # Auto-Seed: Wenn noch keine Leistungen vorhanden, Standard-Katalog laden
    if not items:
        seed_leistungskatalog(current_user.company_id)
        flash('Standard-Leistungskatalog (SGB XI) wurde automatisch geladen.', 'info')
        items = Leistungskatalog.query.filter_by(
            company_id=current_user.company_id
        ).order_by(Leistungskatalog.kategorie, Leistungskatalog.leistung_nr).all()

    return render_template('leistung/katalog.html', items=items)


@leistung_bp.route('/katalog/seed', methods=['POST'])
@login_required
def katalog_seed():
    """Standard SGB XI Katalog neu laden (vorhandene bleiben erhalten)."""
    if not current_user.is_admin:
        return jsonify({'error': 'Keine Berechtigung'}), 403

    existing_nrs = {
        item.leistung_nr
        for item in Leistungskatalog.query.filter_by(company_id=current_user.company_id).all()
    }
    added = 0
    for item in STANDARD_KATALOG:
        if item['leistung_nr'] not in existing_nrs:
            db.session.add(Leistungskatalog(
                company_id=current_user.company_id,
                leistung_nr=item['leistung_nr'],
                bezeichnung=item['bezeichnung'],
                beschreibung=item.get('beschreibung', ''),
                kategorie=item.get('kategorie', ''),
                dauer_minuten=item.get('dauer_minuten'),
                preis=item.get('preis'),
                is_active=True,
            ))
            added += 1
    db.session.commit()
    flash(f'Standard-Katalog aktualisiert: {added} neue Leistungen hinzugefügt.', 'success')
    return redirect(url_for('leistung.katalog_manage'))


def _get_patient(patient_id):
    return Patient.query.filter_by(id=patient_id,
                                   company_id=current_user.company_id,
                                   deleted_at=None).first_or_404()


def _parse_date(value):
    if not value:
        return None
    try:
        return datetime.strptime(value, '%Y-%m-%d').date()
    except Exception:
        return None


def _parse_time(value):
    if not value:
        return None
    try:
        return datetime.strptime(value, '%H:%M').time()
    except Exception:
        return None


def _float(val):
    try:
        return float(val) if val is not None and val != '' else None
    except Exception:
        return None
