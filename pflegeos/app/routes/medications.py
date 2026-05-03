from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app.extensions import db
from app.models import MedicationPlan, Medication, MedicationAdministration, BtmBuch, Patient, Employee
from app.utils.auth import log_action
from app.utils.email import send_btm_alert_email
from datetime import datetime, date, time

medications_bp = Blueprint('medications', __name__)


@medications_bp.route('/patient/<patient_id>')
@login_required
def patient_overview(patient_id):
    p = _get_patient(patient_id)
    plan = MedicationPlan.query.filter_by(
        patient_id=patient_id, is_current=True).first()
    today_administrations = []
    if plan:
        today_administrations = MedicationAdministration.query.filter(
            MedicationAdministration.patient_id == patient_id,
            MedicationAdministration.administered_at >= datetime.combine(date.today(), time.min)
        ).order_by(MedicationAdministration.administered_at.desc()).all()

    return render_template('medications/overview.html',
                           patient=p, plan=plan,
                           today_administrations=today_administrations)


@medications_bp.route('/patient/<patient_id>/plan/new', methods=['GET', 'POST'])
@login_required
def new_plan(patient_id):
    p = _get_patient(patient_id)

    if request.method == 'POST':
        # Деактивируем старый план
        MedicationPlan.query.filter_by(patient_id=patient_id, is_current=True).update({'is_current': False})

        plan = MedicationPlan(
            company_id=current_user.company_id,
            patient_id=patient_id,
            created_by=current_user.id,
            prescribed_by=request.form.get('prescribed_by', '').strip(),
            valid_from=_parse_date(request.form.get('valid_from')) or date.today(),
        )
        db.session.add(plan)
        db.session.flush()

        # Медикаменты из формы (динамические строки)
        meds_count = int(request.form.get('meds_count', 0))
        for i in range(meds_count):
            name = request.form.get(f'med_{i}_handelsname', '').strip()
            if not name:
                continue
            med = Medication(
                medication_plan_id=plan.id,
                handelsname=name,
                wirkstoff=request.form.get(f'med_{i}_wirkstoff', '').strip(),
                staerke=request.form.get(f'med_{i}_staerke', '').strip(),
                darreichungsform=request.form.get(f'med_{i}_form', '').strip(),
                morgens=request.form.get(f'med_{i}_morgens', '').strip(),
                mittags=request.form.get(f'med_{i}_mittags', '').strip(),
                abends=request.form.get(f'med_{i}_abends', '').strip(),
                nachts=request.form.get(f'med_{i}_nachts', '').strip(),
                bei_bedarf=f'med_{i}_bei_bedarf' in request.form,
                einnahmehinweis=request.form.get(f'med_{i}_hinweis', '').strip(),
                is_btm=f'med_{i}_btm' in request.form,
                btm_bestand=float(request.form.get(f'med_{i}_btm_bestand', 0) or 0),
            )
            db.session.add(med)

        db.session.commit()
        log_action('CREATE', 'medication_plans', entity_id=plan.id)
        flash('Medikationsplan gespeichert.', 'success')
        return redirect(url_for('medications.patient_overview', patient_id=patient_id))

    return render_template('medications/plan_form.html', patient=p)


@medications_bp.route('/administer/<medication_id>', methods=['GET', 'POST'])
@login_required
def administer(medication_id):
    med = Medication.query.get_or_404(medication_id)
    plan = MedicationPlan.query.get(med.medication_plan_id)
    p = _get_patient(plan.patient_id)

    if request.method == 'POST':
        fd = request.form

        # Для BtM нужен второй сотрудник
        if med.is_btm:
            verifier_id = fd.get('verifier_id')
            pin2 = fd.get('pin2', '')
            verifier = Employee.query.filter_by(
                id=verifier_id, company_id=current_user.company_id).first()
            if not verifier or not verifier.check_pin(pin2):
                flash('Zweite Bestätigung für BtM fehlgeschlagen.', 'danger')
                return redirect(request.url)

        dosis = fd.get('dosis', '').strip()
        bestaetigt = 'bestaetigt' in fd
        restmenge_nach = float(fd.get('restmenge_nach', 0) or 0)

        admin = MedicationAdministration(
            company_id=current_user.company_id,
            medication_id=medication_id,
            patient_id=plan.patient_id,
            administered_by=current_user.id,
            tatsaechliche_dosis=dosis,
            einnahme_bestaetigt=bestaetigt,
            ablehnung_grund=fd.get('ablehnung_grund', '').strip() if not bestaetigt else None,
            restmenge_vor=med.btm_bestand if med.is_btm else None,
            restmenge_nach=restmenge_nach if med.is_btm else None,
            verification_method='DUAL_PIN' if med.is_btm else 'PIN_MAC_GPS',
            device_mac=fd.get('device_mac', '').strip() or None,
            geo_lat=_float(fd.get('geo_lat')),
            geo_lng=_float(fd.get('geo_lng')),
            bemerkungen=fd.get('bemerkungen', '').strip(),
        )

        if med.is_btm:
            # Обновляем остаток
            med.btm_bestand = restmenge_nach
            # Запись в BtM-Buch
            btm_entry = BtmBuch(
                company_id=current_user.company_id,
                medication_id=medication_id,
                buchungsdatum=date.today(),
                buchungszeit=datetime.utcnow().time(),
                vorgang='ABGANG',
                menge=float(dosis.split()[0]) if dosis else 0,
                einheit=med.darreichungsform or 'Einheit',
                bestand_nach=restmenge_nach,
                patient_id=plan.patient_id,
                mitarbeiter_1_id=current_user.id,
                mitarbeiter_2_id=fd.get('verifier_id', current_user.id),
                geo_lat=_float(fd.get('geo_lat')),
                geo_lng=_float(fd.get('geo_lng')),
            )
            db.session.add(btm_entry)

            # Send BtM alert to employees
            employees = Employee.query.filter_by(company_id=current_user.company_id, deleted_at=None).all()
            pending_entries = [{
                'medication_name': med.handelsname,
                'patient_name': p.full_name,
                'time': datetime.utcnow().strftime('%H:%M')
            }]
            for emp in employees:
                if emp.email:
                    send_btm_alert_email(emp.email, emp.full_name, pending_entries)

        db.session.add(admin)
        db.session.commit()
        log_action('CREATE', 'medication_administrations', entity_id=admin.id)
        flash('Verabreichung dokumentiert.', 'success')
        return redirect(url_for('medications.patient_overview', patient_id=plan.patient_id))

    colleagues = Employee.query.filter_by(
        company_id=current_user.company_id, is_active=True
    ).filter(Employee.id != current_user.id).all() if med.is_btm else []

    return render_template('medications/administer.html',
                           medication=med, patient=p, colleagues=colleagues)


@medications_bp.route('/btm-buch')
@login_required
def btm_buch():
    entries = BtmBuch.query.filter_by(
        company_id=current_user.company_id
    ).order_by(BtmBuch.created_at.desc()).limit(100).all()
    return render_template('medications/btm_buch.html', entries=entries)


def _get_patient(patient_id):
    return Patient.query.filter_by(id=patient_id,
                                   company_id=current_user.company_id,
                                   deleted_at=None).first_or_404()


def _parse_date(value):
    if not value:
        return None
    try:
        return datetime.strptime(value, '%Y-%m-%d').date()
    except (ValueError, TypeError):
        return None


def _float(val):
    try:
        return float(val) if val is not None and val != '' else None
    except (ValueError, TypeError):
        return None
