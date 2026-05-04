"""
Nurse Dashboard - просмотр плана работ и создание отчетов о визитах.
"""

from flask import Blueprint, render_template, request, jsonify, current_app
from flask_login import login_required, current_user
from app.extensions import db
from app.models import (
    Employee, Patient, EmployeeSchedule, VisitReport, PatientPhoto,
    EmployeePatientAssignment, Company
)
from app.utils.auth import log_action
from datetime import datetime, date, timedelta
import json

nurse_bp = Blueprint('nurse', __name__, url_prefix='/nurse')


@nurse_bp.route('/dashboard')
@login_required
def dashboard():
    """Nurse Dashboard - план на сегодня"""
    # Медсестра видит только свой план
    today = date.today()

    # Получаем план на сегодня
    schedules = EmployeeSchedule.query.filter_by(
        employee_id=current_user.id,
        company_id=current_user.company_id,
        scheduled_date=today,
        is_active=True
    ).order_by(EmployeeSchedule.scheduled_time).all()

    # Статистика
    total_visits = len(schedules)
    completed_visits = len([s for s in schedules if s.status == 'COMPLETED'])
    in_progress_visits = len([s for s in schedules if s.status == 'IN_PROGRESS'])
    pending_visits = len([s for s in schedules if s.status == 'PENDING'])

    # Еженедельный план (следующие 7 дней, исключая сегодня)
    week_end = today + timedelta(days=7)
    week_schedules = EmployeeSchedule.query.filter(
        EmployeeSchedule.employee_id == current_user.id,
        EmployeeSchedule.company_id == current_user.company_id,
        EmployeeSchedule.scheduled_date >= today,
        EmployeeSchedule.scheduled_date <= week_end,
        EmployeeSchedule.is_active == True
    ).order_by(
        EmployeeSchedule.scheduled_date,
        EmployeeSchedule.scheduled_time
    ).all()

    return render_template('nurse/dashboard.html',
                         schedules=schedules,
                         week_schedules=week_schedules,
                         today=today,
                         total_visits=total_visits,
                         completed_visits=completed_visits,
                         in_progress_visits=in_progress_visits,
                         pending_visits=pending_visits)


@nurse_bp.route('/schedule/<schedule_id>/start', methods=['POST'])
@login_required
def start_visit(schedule_id):
    """Начать визит (открыть форму отчета с камерой)"""
    schedule = EmployeeSchedule.query.filter_by(
        id=schedule_id,
        employee_id=current_user.id,
        company_id=current_user.company_id,
        is_active=True
    ).first_or_404()

    # Обновляем статус
    schedule.status = 'IN_PROGRESS'
    db.session.commit()

    log_action('VISIT_STARTED', 'EmployeeSchedule', schedule_id, new_values={
        'patient': schedule.patient.full_name,
        'time': datetime.now().isoformat()
    })

    return jsonify({
        'success': True,
        'visit_id': schedule_id,
        'message': f'Визит у {schedule.patient.full_name} начат'
    })


@nurse_bp.route('/schedule/<schedule_id>/report', methods=['GET', 'POST'])
@login_required
def visit_report(schedule_id):
    """Создать/редактировать отчет о визите"""
    schedule = EmployeeSchedule.query.filter_by(
        id=schedule_id,
        employee_id=current_user.id,
        company_id=current_user.company_id,
        is_active=True
    ).first_or_404()

    patient = schedule.patient

    if request.method == 'GET':
        # Получить существующий отчет или создать новый
        if schedule.visit_report_id:
            report = VisitReport.query.get(schedule.visit_report_id)
        else:
            report = None

        # Процедуры из плана
        procedures = json.loads(schedule.procedures or '[]')

        return render_template('nurse/visit_report.html',
                             schedule=schedule,
                             patient=patient,
                             report=report,
                             procedures=procedures)

    elif request.method == 'POST':
        # Сохранить отчет
        try:
            # Получить или создать отчет
            if schedule.visit_report_id:
                report = VisitReport.query.get(schedule.visit_report_id)
            else:
                report = VisitReport()
                report.company_id = current_user.company_id
                report.employee_id = current_user.id
                report.patient_id = patient.id
                report.visit_date = date.today()
                report.visit_start_time = schedule.scheduled_time or datetime.now()

            # Заполнить поля из формы
            report.visit_end_time = datetime.now()
            report.observations = request.form.get('observations', '')
            report.patient_condition = request.form.get('patient_condition', 'STABLE')
            report.procedures_completed = request.form.get('procedures_completed', '[]')
            report.issues_encountered = request.form.get('issues_encountered', '[]')
            report.photo_ids = request.form.get('photo_ids', '[]')

            # GPS данные из формы
            report.geo_lat = request.form.get('geo_lat', type=float)
            report.geo_lng = request.form.get('geo_lng', type=float)
            report.device_mac = request.form.get('device_mac', '')
            report.verification_method = 'MAC_GPS'

            # Подпись
            report.signature_confirmed = request.form.get('signature_confirmed', type=bool)
            report.signature_time = datetime.now() if report.signature_confirmed else None

            # Статус
            report.status = 'SUBMITTED'

            db.session.add(report)
            db.session.flush()

            # Связать с планом
            schedule.visit_report_id = report.id
            schedule.status = 'COMPLETED'
            db.session.commit()

            log_action('VISIT_REPORT_CREATED', 'VisitReport', report.id, new_values={
                'patient': patient.full_name,
                'status': 'SUBMITTED'
            })

            return jsonify({
                'success': True,
                'report_id': report.id,
                'message': 'Отчет о визите сохранен'
            }), 201

        except Exception as e:
            return jsonify({'error': str(e)}), 500


@nurse_bp.route('/schedule/<schedule_id>/cancel', methods=['POST'])
@login_required
def cancel_visit(schedule_id):
    """Отменить визит"""
    schedule = EmployeeSchedule.query.filter_by(
        id=schedule_id,
        employee_id=current_user.id,
        company_id=current_user.company_id,
        is_active=True
    ).first_or_404()

    reason = request.form.get('reason', 'Not specified')

    schedule.status = 'CANCELLED'
    schedule.notes = f"Отменено: {reason}"
    db.session.commit()

    log_action('VISIT_CANCELLED', 'EmployeeSchedule', schedule_id, new_values={
        'patient': schedule.patient.full_name,
        'reason': reason
    })

    return jsonify({
        'success': True,
        'message': f'Визит отменен'
    })


@nurse_bp.route('/reports')
@login_required
def my_reports():
    """Мои отчеты (история)"""
    page = request.args.get('page', 1, type=int)

    reports = VisitReport.query.filter_by(
        employee_id=current_user.id,
        company_id=current_user.company_id,
        is_active=True
    ).order_by(VisitReport.visit_date.desc()).paginate(page=page, per_page=20)

    return render_template('nurse/reports_list.html', reports=reports)


@nurse_bp.route('/reports/<report_id>')
@login_required
def view_report(report_id):
    """Просмотреть отчет о визите"""
    report = VisitReport.query.filter_by(
        id=report_id,
        employee_id=current_user.id,
        company_id=current_user.company_id,
        is_active=True
    ).first_or_404()

    return render_template('nurse/report_detail.html', report=report)


@nurse_bp.route('/schedule/<schedule_id>/photos')
@login_required
def visit_photos(schedule_id):
    """Получить фото для визита (для встраивания в форму)"""
    schedule = EmployeeSchedule.query.filter_by(
        id=schedule_id,
        employee_id=current_user.id,
        company_id=current_user.company_id,
        is_active=True
    ).first_or_404()

    # Фото пациента за последний час
    one_hour_ago = datetime.now() - timedelta(hours=1)
    photos = PatientPhoto.query.filter(
        PatientPhoto.patient_id == schedule.patient_id,
        PatientPhoto.company_id == current_user.company_id,
        PatientPhoto.created_at >= one_hour_ago,
        PatientPhoto.is_active == True
    ).order_by(PatientPhoto.created_at.desc()).all()

    return jsonify([{
        'id': p.id,
        'photo_type': p.photo_type,
        'created_at': p.created_at.isoformat(),
        'url': f"/photos/{p.id}/view-file",
        'description': p.description
    } for p in photos])


@nurse_bp.route('/reports/<report_id>/verify', methods=['POST'])
@login_required
def verify_report(report_id):
    """Администратор подтверждает отчет (меняет статус на VERIFIED)"""
    # Только администраторы могут утверждать отчеты
    if not current_user.is_admin:
        return jsonify({'success': False, 'message': 'Zugriff verweigert'}), 403

    report = VisitReport.query.filter_by(
        id=report_id,
        company_id=current_user.company_id,
        is_active=True
    ).first_or_404()

    report.status = 'VERIFIED'
    report.verified_by = current_user.id
    report.verified_at = datetime.now()
    db.session.commit()

    log_action('VISIT_REPORT_VERIFIED', 'VisitReport', report_id, new_values={
        'patient': report.patient.full_name,
        'verified_by': current_user.full_name
    })

    return jsonify({
        'success': True,
        'message': 'Bericht genehmigt'
    })


@nurse_bp.route('/reports/<report_id>/reject', methods=['POST'])
@login_required
def reject_report(report_id):
    """Администратор отклоняет отчет (меняет статус на DRAFT)"""
    # Только администраторы могут отклонять отчеты
    if not current_user.is_admin:
        return jsonify({'success': False, 'message': 'Zugriff verweigert'}), 403

    try:
        data = request.get_json()
        reason = data.get('reason', 'Not specified')
    except:
        reason = request.form.get('reason', 'Not specified')

    report = VisitReport.query.filter_by(
        id=report_id,
        company_id=current_user.company_id,
        is_active=True
    ).first_or_404()

    report.status = 'DRAFT'
    report.notes = f"Abgelehnt durch {current_user.full_name}: {reason}"
    db.session.commit()

    log_action('VISIT_REPORT_REJECTED', 'VisitReport', report_id, new_values={
        'patient': report.patient.full_name,
        'rejected_by': current_user.full_name,
        'reason': reason
    })

    return jsonify({
        'success': True,
        'message': 'Bericht abgelehnt'
    })
