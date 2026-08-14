"""
Admin Dashboard - управление процедурами, расписаниями, параметрами системы.
"""

from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for, current_app
from flask_login import login_required, current_user
from app.extensions import db
from app.models import (
    Company, Employee, Patient, Procedure, EmployeeSchedule, VisitReport,
    EmployeePatientAssignment, Leistungsnachweis, PatientPhoto, AuditLog,
    SisAssessment, MedicationPlan, WoundDoc, WoundAssessment,
)
from app.utils.auth import admin_required, log_action
from datetime import datetime, date, timedelta
import json

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


# ==================== PROCEDURES MANAGEMENT ====================

@admin_bp.route('/procedures')
@login_required
@admin_required
def procedures_list():
    """Список всех процедур компании"""
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '')

    query = Procedure.query.filter_by(
        company_id=current_user.company_id,
        is_active=True
    )

    if search:
        query = query.filter(
            db.or_(
                Procedure.name.ilike(f'%{search}%'),
                Procedure.description.ilike(f'%{search}%'),
                Procedure.category.ilike(f'%{search}%')
            )
        )

    procedures = query.order_by(Procedure.name).paginate(page=page, per_page=20)

    return render_template('admin/procedures_list.html', procedures=procedures, search=search)


@admin_bp.route('/procedures/create', methods=['GET', 'POST'])
@login_required
@admin_required
def procedure_create():
    """Создать новую процедуру"""
    if request.method == 'POST':
        try:
            name = request.form.get('name', '').strip()
            description = request.form.get('description', '').strip()
            category = request.form.get('category', '').strip()
            duration_minutes = request.form.get('duration_minutes', type=int, default=15)
            required_qualification = request.form.get('required_qualification', '').strip()
            requires_verification = request.form.get('requires_verification') == 'on'

            if not name:
                return jsonify({'error': 'Name erforderlich'}), 400

            if duration_minutes < 1:
                return jsonify({'error': 'Dauer mindestens 1 Minute'}), 400

            procedure = Procedure(
                company_id=current_user.company_id,
                name=name,
                description=description,
                category=category,
                duration_minutes=duration_minutes,
                required_qualification=required_qualification,
                requires_verification=requires_verification
            )

            db.session.add(procedure)
            db.session.commit()

            log_action('PROCEDURE_CREATED', 'Procedure', procedure.id, new_values={
                'name': name,
                'category': category
            })

            flash(f'Verfahren "{name}" erstellt', 'success')
            return redirect(url_for('admin.procedures_list'))

        except Exception as e:
            return jsonify({'error': str(e)}), 500

    return render_template('admin/procedure_form.html', procedure=None)


@admin_bp.route('/procedures/<procedure_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def procedure_edit(procedure_id):
    """Редактировать процедуру"""
    procedure = Procedure.query.filter_by(
        id=procedure_id,
        company_id=current_user.company_id,
        is_active=True
    ).first_or_404()

    if request.method == 'POST':
        try:
            old_values = {
                'name': procedure.name,
                'category': procedure.category,
                'duration_minutes': procedure.duration_minutes
            }

            procedure.name = request.form.get('name', '').strip()
            procedure.description = request.form.get('description', '').strip()
            procedure.category = request.form.get('category', '').strip()
            procedure.duration_minutes = request.form.get('duration_minutes', type=int, default=15)
            procedure.required_qualification = request.form.get('required_qualification', '').strip()
            procedure.requires_verification = request.form.get('requires_verification') == 'on'

            if not procedure.name:
                return jsonify({'error': 'Name erforderlich'}), 400

            if procedure.duration_minutes < 1:
                return jsonify({'error': 'Dauer mindestens 1 Minute'}), 400

            db.session.commit()

            log_action('PROCEDURE_UPDATED', 'Procedure', procedure.id,
                      old_values=old_values,
                      new_values={'name': procedure.name, 'category': procedure.category})

            flash(f'Verfahren "{procedure.name}" aktualisiert', 'success')
            return redirect(url_for('admin.procedures_list'))

        except Exception as e:
            return jsonify({'error': str(e)}), 500

    return render_template('admin/procedure_form.html', procedure=procedure)


@admin_bp.route('/procedures/<procedure_id>/delete', methods=['POST'])
@login_required
@admin_required
def procedure_delete(procedure_id):
    """Soft-delete процедуры"""
    procedure = Procedure.query.filter_by(
        id=procedure_id,
        company_id=current_user.company_id
    ).first_or_404()

    procedure.is_active = False
    db.session.commit()

    log_action('PROCEDURE_DELETED', 'Procedure', procedure_id,
              old_values={'name': procedure.name})

    flash(f'Verfahren "{procedure.name}" gelöscht', 'success')
    return redirect(url_for('admin.procedures_list'))


# ==================== SCHEDULE GENERATION ====================

@admin_bp.route('/schedules')
@login_required
@admin_required
def schedules_list():
    """Список созданных расписаний"""
    page = request.args.get('page', 1, type=int)

    from app.models import ScheduleGeneration

    schedules = ScheduleGeneration.query.filter_by(
        company_id=current_user.company_id
    ).order_by(ScheduleGeneration.created_at.desc()).paginate(page=page, per_page=20)

    return render_template('admin/schedules_list.html', schedules=schedules)


@admin_bp.route('/schedules/generate', methods=['GET', 'POST'])
@login_required
@admin_required
def schedule_generate():
    """Генерировать расписание (запрос к Claude AI)"""
    if request.method == 'POST':
        try:
            schedule_start_date = request.form.get('schedule_start_date', type=lambda x: datetime.strptime(x, '%Y-%m-%d').date())
            schedule_end_date = request.form.get('schedule_end_date', type=lambda x: datetime.strptime(x, '%Y-%m-%d').date())
            employee_ids = request.form.getlist('employee_ids')
            patient_ids = request.form.getlist('patient_ids')
            anonymize_for_ai = request.form.get('anonymize_for_ai') == 'on'

            if not schedule_start_date or not schedule_end_date:
                return jsonify({'error': 'Datumsbereich erforderlich'}), 400

            if schedule_start_date > schedule_end_date:
                return jsonify({'error': 'Startdatum muss vor Enddatum liegen'}), 400

            if not employee_ids or not patient_ids:
                return jsonify({'error': 'Mindestens ein Mitarbeiter und ein Patient erforderlich'}), 400

            # Получить данные для AI анализа
            employees = Employee.query.filter(
                Employee.id.in_(employee_ids),
                Employee.company_id == current_user.company_id
            ).all()

            patients = Patient.query.filter(
                Patient.id.in_(patient_ids),
                Patient.company_id == current_user.company_id
            ).all()

            # Построить промпт для Claude (+ получить маппинги)
            ai_prompt_text, employee_map, patient_map = _build_schedule_prompt(
                employees=employees,
                patients=patients,
                schedule_start_date=schedule_start_date,
                schedule_end_date=schedule_end_date,
                anonymize=anonymize_for_ai
            )

            # Сохраняем prompt + маппинги вместе (для де-анонимизации при approve)
            ai_prompt_envelope = json.dumps({
                'prompt':       ai_prompt_text,
                'employee_map': employee_map,   # {'NURSE_1': real_uuid, ...}
                'patient_map':  patient_map,    # {'PATIENT_1': real_uuid, ...}
            }, ensure_ascii=False)

            # Вызвать Claude API
            ai_response = _call_claude_api(ai_prompt_text)

            if not ai_response:
                return jsonify({'error': 'Fehler beim Kontakt mit Claude AI'}), 500

            # Сохранить ScheduleGeneration запись
            from app.models import ScheduleGeneration

            schedule_gen = ScheduleGeneration(
                company_id=current_user.company_id,
                created_by=current_user.id,
                schedule_start_date=schedule_start_date,
                schedule_end_date=schedule_end_date,
                ai_prompt=ai_prompt_envelope,   # JSON envelope с маппингами
                ai_response=ai_response,
                status='GENERATED',
                anonymize_for_ai=anonymize_for_ai
            )

            db.session.add(schedule_gen)
            db.session.commit()

            log_action('SCHEDULE_GENERATED', 'ScheduleGeneration', schedule_gen.id, new_values={
                'date_range': f"{schedule_start_date} to {schedule_end_date}",
                'employees': len(employees),
                'patients': len(patients)
            })

            flash(f'Zeitplan für {schedule_start_date} bis {schedule_end_date} generiert', 'success')
            return redirect(url_for('admin.schedule_review', schedule_gen_id=schedule_gen.id))

        except Exception as e:
            return jsonify({'error': str(e)}), 500

    # GET: показать форму генерации
    employees = Employee.query.filter_by(
        company_id=current_user.company_id,
        is_active=True
    ).order_by(Employee.vorname).all()

    patients = Patient.query.filter(
        Patient.company_id == current_user.company_id,
        Patient.deleted_at.is_(None)
    ).order_by(Patient.nachname).all()

    return render_template('admin/schedule_generate.html', employees=employees, patients=patients)


@admin_bp.route('/schedules/<schedule_gen_id>/review')
@login_required
@admin_required
def schedule_review(schedule_gen_id):
    """Просмотр и утверждение сгенерированного расписания"""
    from app.models import ScheduleGeneration

    schedule_gen = ScheduleGeneration.query.filter_by(
        id=schedule_gen_id,
        company_id=current_user.company_id
    ).first_or_404()

    # Парсинг AI ответа и трансформация в flat list для шаблона
    try:
        raw_plan = json.loads(schedule_gen.ai_response)
    except Exception:
        raw_plan = {}

    # Загрузить маппинги из envelope (для де-анонимизации)
    employee_map = {}
    patient_map  = {}
    try:
        envelope = json.loads(schedule_gen.ai_prompt or '{}')
        employee_map = envelope.get('employee_map', {})  # NURSE_N → real_uuid
        patient_map  = envelope.get('patient_map',  {})  # PATIENT_N → real_uuid
    except Exception:
        pass

    # Инвертированные маппинги: real_uuid → anon_id (для обратного поиска)
    # + реальные объекты по UUID
    emp_by_id = {str(e.id): e for e in Employee.query.filter_by(
        company_id=current_user.company_id
    ).all()}
    pat_by_id = {str(p.id): p for p in Patient.query.filter(
        Patient.company_id == current_user.company_id,
        Patient.deleted_at.is_(None)
    ).all()}

    def resolve_employee(raw_id):
        """NURSE_N или real_uuid → Employee объект"""
        if raw_id.startswith('NURSE_'):
            real_id = employee_map.get(raw_id, '')
            return emp_by_id.get(real_id)
        return emp_by_id.get(raw_id)

    def resolve_patient(raw_id):
        """PATIENT_N или real_uuid → Patient объект"""
        if raw_id.startswith('PATIENT_'):
            real_id = patient_map.get(raw_id, '')
            return pat_by_id.get(real_id)
        return pat_by_id.get(raw_id)

    # Flatten: AI response → список визитов для шаблона
    ai_plan = []
    for item in raw_plan.get('schedule', []):
        nurse_raw = item.get('nurse_id', '')
        nurse = resolve_employee(nurse_raw)
        emp_name = nurse.full_name if nurse else f'Unbekannt ({nurse_raw})'
        date_str = item.get('date', '')

        for visit in item.get('visits', []):
            patient_raw = visit.get('patient_id', '')
            patient = resolve_patient(patient_raw)
            pat_name = patient.full_name if patient else f'Unbekannt ({patient_raw})'

            risk_flags = []
            if patient:
                if patient.sturzrisiko:    risk_flags.append('Sturzrisiko')
                if patient.dekubitusrisiko: risk_flags.append('Dekubitusrisiko')

            ai_plan.append({
                'date':             date_str,
                'employee_name':    emp_name,
                'employee_id':      nurse_raw,
                'patient_name':     pat_name,
                'patient_id':       patient_raw,
                'scheduled_time':   visit.get('time', '09:00'),
                'duration_minutes': visit.get('duration_minutes', 30),
                'procedures':       [],
                'patient_location': patient.ort if patient else None,
                'care_level':       patient.pflegegrad if patient else None,
                'patient_risk_level': ', '.join(risk_flags) if risk_flags else None,
                'notes':            visit.get('reason', ''),
            })

    ai_notes = raw_plan.get('notes', '')

    return render_template('admin/schedule_review.html',
                           schedule_gen=schedule_gen,
                           ai_plan=ai_plan,
                           ai_notes=ai_notes)


@admin_bp.route('/schedules/<schedule_gen_id>/approve', methods=['POST'])
@login_required
@admin_required
def schedule_approve(schedule_gen_id):
    """Утвердить сгенерированное расписание"""
    from app.models import ScheduleGeneration

    schedule_gen = ScheduleGeneration.query.filter_by(
        id=schedule_gen_id,
        company_id=current_user.company_id
    ).first_or_404()

    # Status-Check case-insensitiv (DB kann 'generated' oder 'GENERATED' enthalten)
    if schedule_gen.status.upper() not in ('GENERATED', 'PENDING_REVIEW'):
        flash(f'Dieser Zeitplan kann nicht genehmigt werden (Status: {schedule_gen.status}).', 'warning')
        return redirect(url_for('admin.schedules_list'))

    try:
        approval_notes = request.form.get('approval_notes', '')

        # Парсинг AI плана и создание EmployeeSchedule записей
        ai_plan = json.loads(schedule_gen.ai_response)
        schedules_created = _create_schedules_from_plan(schedule_gen, ai_plan)

        schedule_gen.status = 'APPROVED'
        schedule_gen.approved_by = current_user.id
        schedule_gen.approved_at = datetime.now()
        schedule_gen.approval_notes = approval_notes
        schedule_gen.schedules_created = schedules_created

        db.session.commit()

        log_action('SCHEDULE_APPROVED', 'ScheduleGeneration', schedule_gen_id, new_values={
            'schedules_created': schedules_created,
            'approval_notes': approval_notes
        })

        flash(f'Zeitplan genehmigt! {schedules_created} Einsätze erstellt.', 'success')
        return redirect(url_for('admin.schedule_distribute', schedule_gen_id=schedule_gen_id))

    except Exception as e:
        current_app.logger.error(f"Approve error: {str(e)}")
        flash(f'Fehler beim Genehmigen: {str(e)}', 'danger')
        return redirect(url_for('admin.schedule_review', schedule_gen_id=schedule_gen_id))


@admin_bp.route('/schedules/<schedule_gen_id>/distribute', methods=['GET', 'POST'])
@login_required
@admin_required
def schedule_distribute(schedule_gen_id):
    """Распределить расписание между медсестрами"""
    from app.models import ScheduleGeneration

    schedule_gen = ScheduleGeneration.query.filter_by(
        id=schedule_gen_id,
        company_id=current_user.company_id
    ).first_or_404()

    # Status-Check case-insensitiv
    if schedule_gen.status.upper() != 'APPROVED':
        if request.method == 'POST':
            return jsonify({'success': False, 'error': 'Nur genehmigte Zeitpläne können verteilt werden'}), 400
        flash('Dieser Zeitplan ist nicht genehmigt.', 'warning')
        return redirect(url_for('admin.schedules_list'))

    if request.method == 'POST':
        try:
            # Einsätze für den Zeitraum
            schedules_to_send = EmployeeSchedule.query.filter(
                EmployeeSchedule.company_id == current_user.company_id,
                EmployeeSchedule.scheduled_date >= schedule_gen.schedule_start_date,
                EmployeeSchedule.scheduled_date <= schedule_gen.schedule_end_date,
                EmployeeSchedule.is_active == True
            ).all()

            employees_notified = len(set(s.employee_id for s in schedules_to_send))

            # Статус плана → DISTRIBUTED, EmployeeSchedule → is_active уже True
            schedule_gen.status = 'DISTRIBUTED'
            schedule_gen.distributed_at = datetime.now()
            schedule_gen.distributed_to_count = employees_notified
            db.session.commit()

            log_action('SCHEDULE_DISTRIBUTED', 'ScheduleGeneration', schedule_gen_id, new_values={
                'distributed_to': employees_notified,
                'assignments': len(schedules_to_send)
            })

            # Возвращаем JSON — фронтенд сам редиректит
            return jsonify({
                'success': True,
                'employees_notified': employees_notified,
                'assignments': len(schedules_to_send),
                'email_sent': False,   # TODO: подключить email
                'push_sent': True,     # план виден в дашборде
                'sms_sent': False,
                'redirect_url': url_for('admin.schedules_list')
            })

        except Exception as e:
            current_app.logger.error(f"Distribute error: {str(e)}")
            return jsonify({'success': False, 'error': str(e)}), 500

    return render_template('admin/schedule_distribute.html', schedule_gen=schedule_gen)


# ==================== HELPER FUNCTIONS ====================

def _build_schedule_prompt(employees, patients, schedule_start_date, schedule_end_date, anonymize=True):
    """Построить промпт для Claude API.
    Returns (prompt_str, employee_map, patient_map)
    где employee_map: {'NURSE_1': real_emp_id, ...}
    """
    employee_map = {}   # NURSE_N → real employee.id
    patient_map  = {}   # PATIENT_N → real patient.id

    employee_data = []
    for i, emp in enumerate(employees, start=1):
        anon_id = f'NURSE_{i}'
        employee_map[anon_id] = emp.id
        emp_info = {
            'id':   emp.id   if not anonymize else anon_id,
            'name': emp.full_name if not anonymize else f'Nurse {i}',
            'role': emp.role,
            'qualifications': [q for q in [emp.qualification] if q],
            'max_patients_per_day': 8,
        }
        employee_data.append(emp_info)

    patient_data = []
    for i, pat in enumerate(patients, start=1):
        anon_id = f'PATIENT_{i}'
        patient_map[anon_id] = pat.id
        pat_info = {
            'id':   pat.id   if not anonymize else anon_id,
            'name': pat.full_name if not anonymize else f'Patient {i}',
            'location': {
                'street':    pat.strasse if not anonymize else 'Location',
                'city':      pat.ort     if not anonymize else 'City',
                'latitude':  getattr(pat, 'geo_lat', None),
                'longitude': getattr(pat, 'geo_lng', None),
            },
            'care_type':   pat.care_type,
            'pflegegrad':  pat.pflegegrad,
            'risks': {
                'fall_risk':           bool(pat.sturzrisiko),
                'pressure_ulcer_risk': bool(pat.dekubitusrisiko),
            },
            'visit_frequency_per_week': 3,
        }
        patient_data.append(pat_info)

    prompt = f"""Sie sind ein erfahrener Pflegedienstplaner in Deutschland.
Erstellen Sie einen optimierten Wochendienstplan (Heimbesuchsplan) für das Pflegepersonal.

PLANUNGSZEITRAUM: {schedule_start_date} bis {schedule_end_date}
PFLEGEKRÄFTE: {len(employees)}
PATIENTEN: {len(patients)}

ANFORDERUNGEN:
1. Routenoptimierung: geografisch nahe Patienten zum selben Pflegekraft zuweisen
2. Qualifikationen beachten (PFLEGEFACHKRAFT für Behandlungspflege, PFLEGEHILFSKRAFT für Grundpflege)
3. Gleichmäßige Auslastung — max. 8 Patienten pro Pflegekraft pro Tag
4. Risikomarkierungen beachten (fall_risk / pressure_ulcer_risk → mehr Zeit einplanen)
5. Jeden Tag des Zeitraums planen
6. Uhrzeiten zwischen 07:00 und 18:00, realistisch gestaffelt

PFLEGEKRÄFTE-DATEN:
{json.dumps(employee_data, ensure_ascii=False, indent=2)}

PATIENTEN-DATEN:
{json.dumps(patient_data, ensure_ascii=False, indent=2)}

ANTWORTFORMAT — nur gültiges JSON, keine Erklärungen davor/danach:
{{
  "schedule": [
    {{
      "date": "YYYY-MM-DD",
      "nurse_id": "<id aus Pflegekräfte-Daten>",
      "visits": [
        {{
          "patient_id": "<id aus Patienten-Daten>",
          "time": "HH:MM",
          "duration_minutes": 45,
          "reason": "Kurze Begründung auf Deutsch"
        }}
      ]
    }}
  ],
  "notes": "Empfehlungen und Hinweise auf Deutsch"
}}
"""
    return prompt, employee_map, patient_map


def _call_claude_api(prompt):
    """Вызов Claude API для генерации расписания"""
    try:
        import anthropic

        client = anthropic.Anthropic(api_key=current_app.config.get('ANTHROPIC_API_KEY'))

        message = client.messages.create(
            model="claude-opus-4-5",
            max_tokens=4096,
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )

        # Извлечь JSON из ответа
        response_text = message.content[0].text

        # Попытаться найти JSON в ответе
        import re
        json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
        if json_match:
            json_str = json_match.group(0)
            # Проверить валидность JSON
            json.loads(json_str)
            return json_str

        # Если JSON не найден, попытаться парсить как есть
        json.loads(response_text)
        return response_text

    except Exception as e:
        current_app.logger.error(f"Claude API error: {str(e)}")
        return None


def _create_schedules_from_plan(schedule_gen, ai_plan):
    """Создать EmployeeSchedule записи из AI плана с корректной де-анонимизацией."""
    schedules_created = 0

    # Загрузить маппинги из сохранённого промпта
    employee_map = {}
    patient_map  = {}
    try:
        envelope = json.loads(schedule_gen.ai_prompt or '{}')
        employee_map = envelope.get('employee_map', {})
        patient_map  = envelope.get('patient_map',  {})
    except Exception:
        pass  # Если промпт не JSON — маппинги пустые (режим без анонимизации)

    try:
        if 'schedule' not in ai_plan:
            return 0

        for day_plan in ai_plan['schedule']:
            try:
                schedule_date = datetime.strptime(day_plan['date'], '%Y-%m-%d').date()
            except Exception:
                continue

            raw_nurse_id = day_plan.get('nurse_id', '')

            # Де-анонимизировать NURSE_N → real UUID
            if raw_nurse_id.startswith('NURSE_'):
                nurse_id = employee_map.get(raw_nurse_id)
                if not nurse_id:
                    current_app.logger.warning(f"No mapping for {raw_nurse_id}")
                    continue
            else:
                nurse_id = raw_nurse_id  # Уже реальный UUID

            # Проверить, что медсестра существует
            nurse = Employee.query.filter_by(
                id=nurse_id,
                company_id=current_user.company_id,
                is_active=True
            ).first()
            if not nurse:
                current_app.logger.warning(f"Nurse {nurse_id} not found")
                continue

            for visit in day_plan.get('visits', []):
                raw_patient_id = visit.get('patient_id', '')

                # Де-анонимизировать PATIENT_N → real UUID
                if raw_patient_id.startswith('PATIENT_'):
                    patient_id = patient_map.get(raw_patient_id)
                    if not patient_id:
                        current_app.logger.warning(f"No mapping for {raw_patient_id}")
                        continue
                else:
                    patient_id = raw_patient_id

                # Проверить пациента
                patient = Patient.query.filter(
                    Patient.id == patient_id,
                    Patient.company_id == current_user.company_id,
                    Patient.deleted_at.is_(None)
                ).first()
                if not patient:
                    current_app.logger.warning(f"Patient {patient_id} not found")
                    continue

                # Создать EmployeeSchedule
                try:
                    sched_time = datetime.strptime(visit.get('time', '09:00'), '%H:%M').time()
                except Exception:
                    sched_time = datetime.strptime('09:00', '%H:%M').time()

                schedule = EmployeeSchedule(
                    company_id=current_user.company_id,
                    employee_id=nurse_id,
                    patient_id=patient_id,
                    scheduled_date=schedule_date,
                    scheduled_time=sched_time,
                    address_strasse=patient.strasse,
                    address_hausnummer=patient.hausnummer,
                    address_plz=patient.plz,
                    address_ort=patient.ort,
                    patient_geo_lat=getattr(patient, 'geo_lat', None),
                    patient_geo_lng=getattr(patient, 'geo_lng', None),
                    notes=visit.get('reason', ''),
                    procedures='[]',
                    status='PENDING',
                    is_active=True,
                )
                db.session.add(schedule)
                schedules_created += 1

        db.session.commit()

    except Exception as e:
        current_app.logger.error(f"Error creating schedules: {str(e)}")
        db.session.rollback()

    return schedules_created


# ==================== ADMIN BERICHTE ====================

@admin_bp.route('/reports')
@login_required
@admin_required
def reports_list():
    """Admin: Übersicht aller Visitenberichte + Leistungsnachweise"""
    cid = current_user.company_id

    # Filter-Parameter
    date_from_str = request.args.get('date_from', '')
    date_to_str   = request.args.get('date_to', '')
    employee_id   = request.args.get('employee_id', '')
    status_filter = request.args.get('status', '')

    # ── VisitReports ──
    vr_q = VisitReport.query.filter_by(company_id=cid, is_active=True)
    if date_from_str:
        try:
            vr_q = vr_q.filter(VisitReport.visit_date >= date.fromisoformat(date_from_str))
        except ValueError:
            pass
    if date_to_str:
        try:
            vr_q = vr_q.filter(VisitReport.visit_date <= date.fromisoformat(date_to_str))
        except ValueError:
            pass
    if employee_id:
        vr_q = vr_q.filter(VisitReport.employee_id == employee_id)
    if status_filter:
        vr_q = vr_q.filter(VisitReport.status == status_filter)
    visit_reports = vr_q.order_by(VisitReport.visit_date.desc()).all()

    # Fotos für VisitReports
    visit_photo_map = {}
    for vr in visit_reports:
        try:
            import json as _j
            ids = _j.loads(vr.photo_ids or '[]')
            if ids:
                visit_photo_map[vr.id] = PatientPhoto.query.filter(
                    PatientPhoto.id.in_(ids), PatientPhoto.is_active == True
                ).all()
        except Exception:
            pass

    # ── Leistungsnachweise ──
    ln_q = Leistungsnachweis.query.filter_by(company_id=cid)
    if date_from_str:
        try:
            ln_q = ln_q.filter(Leistungsnachweis.durchgefuehrt_am >= date.fromisoformat(date_from_str))
        except ValueError:
            pass
    if date_to_str:
        try:
            ln_q = ln_q.filter(Leistungsnachweis.durchgefuehrt_am <= date.fromisoformat(date_to_str))
        except ValueError:
            pass
    if employee_id:
        ln_q = ln_q.filter(Leistungsnachweis.employee_id == employee_id)
    if status_filter == 'VERIFIED':
        ln_q = ln_q.filter(Leistungsnachweis.abgerechnet == True)
    elif status_filter == 'SUBMITTED':
        ln_q = ln_q.filter(Leistungsnachweis.abgerechnet == False)
    leistungen = ln_q.order_by(Leistungsnachweis.durchgefuehrt_am.desc()).all()

    # Fotos für Leistungsnachweise (via tags: 'nachweis:<id>')
    leistung_photo_map = {}
    for ln in leistungen:
        photos = PatientPhoto.query.filter(
            PatientPhoto.tags.like(f'%nachweis:{ln.id}%'),
            PatientPhoto.company_id == cid,
            PatientPhoto.is_active == True
        ).all()
        if photos:
            leistung_photo_map[ln.id] = photos

    # Mitarbeiterliste für Filter
    employees = Employee.query.filter_by(
        company_id=cid, is_active=True
    ).order_by(Employee.nachname).all()

    # Statistik
    stats = {
        'total_visits':    len(visit_reports),
        'pending_visits':  sum(1 for r in visit_reports if r.status in ('DRAFT', 'SUBMITTED')),
        'verified_visits': sum(1 for r in visit_reports if r.status == 'VERIFIED'),
        'total_leistung':  len(leistungen),
        'pending_leistung': sum(1 for l in leistungen if not l.abgerechnet),
    }

    return render_template('admin/reports.html',
                           visit_reports=visit_reports,
                           leistungen=leistungen,
                           visit_photo_map=visit_photo_map,
                           leistung_photo_map=leistung_photo_map,
                           employees=employees,
                           stats=stats,
                           date_from=date_from_str,
                           date_to=date_to_str,
                           sel_employee=employee_id,
                           sel_status=status_filter)


@admin_bp.route('/reports/visit/<report_id>/verify', methods=['POST'])
@login_required
@admin_required
def verify_visit_report(report_id):
    """Admin bestätigt einen Visitenbericht."""
    report = VisitReport.query.filter_by(
        id=report_id, company_id=current_user.company_id, is_active=True
    ).first_or_404()

    report.status = 'VERIFIED'
    report.verified_by = current_user.id
    report.verified_at = datetime.now()
    db.session.commit()

    log_action('VISIT_REPORT_VERIFIED', 'VisitReport', report_id, new_values={
        'patient': report.patient.full_name,
        'verified_by': current_user.full_name
    })
    return jsonify({'success': True, 'new_status': 'VERIFIED'})


@admin_bp.route('/reports/visit/<report_id>/reject', methods=['POST'])
@login_required
@admin_required
def reject_visit_report(report_id):
    """Admin lehnt einen Visitenbericht ab."""
    data = request.get_json(silent=True) or {}
    reason = data.get('reason', 'Kein Grund angegeben')

    report = VisitReport.query.filter_by(
        id=report_id, company_id=current_user.company_id, is_active=True
    ).first_or_404()

    report.status = 'DRAFT'
    report.verification_notes = f"Abgelehnt von {current_user.full_name}: {reason}"
    db.session.commit()

    log_action('VISIT_REPORT_REJECTED', 'VisitReport', report_id, new_values={
        'reason': reason, 'by': current_user.full_name
    })
    return jsonify({'success': True, 'new_status': 'DRAFT'})


@admin_bp.route('/reports/leistung/<ln_id>/confirm', methods=['POST'])
@login_required
@admin_required
def confirm_leistung(ln_id):
    """Admin bestätigt einen Leistungsnachweis (abgerechnet = True)."""
    ln = Leistungsnachweis.query.filter_by(
        id=ln_id, company_id=current_user.company_id
    ).first_or_404()

    ln.abgerechnet = True
    db.session.commit()

    log_action('LEISTUNG_CONFIRMED', 'Leistungsnachweis', ln_id, new_values={
        'patient': ln.patient.full_name,
        'leistung': ln.leistung.bezeichnung if ln.leistung else '?',
        'confirmed_by': current_user.full_name
    })
    return jsonify({'success': True})


@admin_bp.route('/reports/leistung/<ln_id>/unconfirm', methods=['POST'])
@login_required
@admin_required
def unconfirm_leistung(ln_id):
    """Admin widerruft Bestätigung eines Leistungsnachweises."""
    ln = Leistungsnachweis.query.filter_by(
        id=ln_id, company_id=current_user.company_id
    ).first_or_404()

    ln.abgerechnet = False
    db.session.commit()

    log_action('LEISTUNG_UNCONFIRMED', 'Leistungsnachweis', ln_id)
    return jsonify({'success': True})


# ── AuditLog-Viewer ────────────────────────────────────────────────────────────

@admin_bp.route('/auditlog')
@login_required
@admin_required
def auditlog():
    page = request.args.get('page', 1, type=int)
    action_filter = request.args.get('action', '').strip()
    user_filter   = request.args.get('user_id', '').strip()

    q = AuditLog.query.filter_by(company_id=current_user.company_id)
    if action_filter:
        q = q.filter(AuditLog.action.ilike(f'%{action_filter}%'))
    if user_filter:
        q = q.filter(AuditLog.user_id == user_filter)

    pagination = q.order_by(AuditLog.created_at.desc()).paginate(
        page=page, per_page=50, error_out=False
    )

    # Mitarbeiter-Map für Namen-Auflösung
    employee_ids = {e.user_id for e in pagination.items if e.user_id}
    employees = {e.id: e for e in Employee.query.filter(
        Employee.id.in_(employee_ids)
    ).all()} if employee_ids else {}

    staff = Employee.query.filter_by(
        company_id=current_user.company_id, deleted_at=None
    ).order_by(Employee.nachname).all()

    return render_template('admin/auditlog.html',
                           pagination=pagination,
                           entries=pagination.items,
                           employees=employees,
                           staff=staff,
                           action_filter=action_filter,
                           user_filter=user_filter)


# ── Alerts / Fehlende Dokumentation ───────────────────────────────────────────

@admin_bp.route('/alerts')
@login_required
@admin_required
def alerts():
    cid = current_user.company_id
    today = date.today()

    patients = Patient.query.filter_by(
        company_id=cid, status='AKTIV', deleted_at=None
    ).order_by(Patient.nachname).all()

    alerts_list = []
    for patient in patients:
        issues = []

        # Kein aktuelles SIS
        sis_current = SisAssessment.query.filter_by(
            patient_id=patient.id, is_current=True
        ).first()
        if not sis_current:
            issues.append({'typ': 'warning', 'text': 'Kein aktuelles SIS vorhanden'})

        # Kein aktiver Medikamentenplan
        med_plan = MedicationPlan.query.filter_by(
            patient_id=patient.id, is_active=True
        ).first()
        if not med_plan:
            issues.append({'typ': 'info', 'text': 'Kein aktiver Medikamentenplan'})

        # Letzte Leistung > 7 Tage alt
        last_ln = Leistungsnachweis.query.filter_by(
            patient_id=patient.id
        ).order_by(Leistungsnachweis.datum.desc()).first()
        if not last_ln or (today - last_ln.datum).days > 7:
            days = (today - last_ln.datum).days if last_ln else None
            msg = f'Letzter Leistungsnachweis vor {days} Tagen' if days else 'Noch kein Leistungsnachweis'
            issues.append({'typ': 'danger', 'text': msg})

        # Offene Wunddokumentation (Wunde ohne aktuelle Beurteilung ≤ 3 Tage)
        open_wounds = WoundDoc.query.filter_by(
            patient_id=patient.id, is_active=True
        ).all()
        for w in open_wounds:
            latest_a = WoundAssessment.query.filter_by(
                wound_id=w.id
            ).order_by(WoundAssessment.assessment_date.desc()).first()
            if not latest_a or (today - latest_a.assessment_date).days > 3:
                issues.append({'typ': 'danger', 'text': f'Wunde "{w.lokalisation}" ohne aktuelle Beurteilung'})

        if issues:
            alerts_list.append({'patient': patient, 'issues': issues})

    return render_template('admin/alerts.html',
                           alerts_list=alerts_list,
                           total_patients=len(patients),
                           today=today)
