"""
Управление назначениями пациентов медсёстрам.
Только для ADMIN.
"""

from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from app.extensions import db
from app.models import Employee, Patient, EmployeePatientAssignment
from app.utils.auth import admin_required, log_action

assignments_bp = Blueprint('assignments', __name__, url_prefix='/assignments')


@assignments_bp.route('/', methods=['GET'])
@login_required
@admin_required
def index():
    """Список всех назначений пациентов."""
    company_id = current_user.company_id

    # Получить все активные назначения
    assignments = EmployeePatientAssignment.query.filter_by(
        company_id=company_id,
        is_active=True
    ).all()

    # Получить список всех медсестер и пациентов для UI
    employees = Employee.query.filter_by(
        company_id=company_id,
        is_active=True,
        deleted_at=None
    ).filter(
        Employee.role.in_(['PFLEGEFACHKRAFT', 'PFLEGEHILFSKRAFT', 'BEHANDLUNGSPFLEGE'])
    ).all()

    patients = Patient.query.filter_by(
        company_id=company_id,
        status='AKTIV',
        deleted_at=None
    ).all()

    return render_template('assignments/index.html',
                          assignments=assignments,
                          employees=employees,
                          patients=patients)


@assignments_bp.route('/create', methods=['POST'])
@login_required
@admin_required
def create():
    """Назначить пациента медсестре."""
    company_id = current_user.company_id
    employee_id = request.form.get('employee_id')
    patient_id = request.form.get('patient_id')
    role = request.form.get('role', 'PRIMARY_NURSE')

    # Валидация
    if not employee_id or not patient_id:
        flash('Пожалуйста заполните все поля.', 'danger')
        return redirect(url_for('assignments.index'))

    # Проверить что сотрудник и пациент существуют и принадлежат компании
    employee = Employee.query.filter_by(id=employee_id, company_id=company_id).first()
    patient = Patient.query.filter_by(id=patient_id, company_id=company_id).first()

    if not employee or not patient:
        flash('Сотрудник или пациент не найден.', 'danger')
        return redirect(url_for('assignments.index'))

    # Проверить есть ли уже такое назначение
    existing = EmployeePatientAssignment.query.filter_by(
        employee_id=employee_id,
        patient_id=patient_id,
        is_active=True
    ).first()

    if existing:
        flash(f'{employee.full_name} уже назначен на {patient.full_name}', 'info')
        return redirect(url_for('assignments.index'))

    # Создать новое назначение
    assignment = EmployeePatientAssignment(
        company_id=company_id,
        employee_id=employee_id,
        patient_id=patient_id,
        role=role,
        assigned_by=current_user.id
    )

    db.session.add(assignment)
    db.session.commit()

    log_action('ASSIGNMENT_CREATED', 'EmployeePatientAssignment', assignment.id,
               new_values={'employee': employee.full_name, 'patient': patient.full_name})

    flash(f'{employee.full_name} назначен на {patient.full_name}', 'success')
    return redirect(url_for('assignments.index'))


@assignments_bp.route('/<assignment_id>/remove', methods=['POST'])
@login_required
@admin_required
def remove(assignment_id):
    """Отозвать назначение."""
    company_id = current_user.company_id

    assignment = EmployeePatientAssignment.query.filter_by(
        id=assignment_id,
        company_id=company_id
    ).first_or_404()

    employee_name = assignment.employee.full_name
    patient_name = assignment.patient.full_name

    # Деактивировать назначение
    assignment.is_active = False
    assignment.unassigned_at = db.func.now()
    assignment.unassigned_by = current_user.id

    db.session.commit()

    log_action('ASSIGNMENT_REMOVED', 'EmployeePatientAssignment', assignment_id,
               old_values={'employee': employee_name, 'patient': patient_name})

    flash(f'Назначение {employee_name} → {patient_name} отозвано', 'success')
    return redirect(url_for('assignments.index'))


@assignments_bp.route('/api/employee/<employee_id>/patients', methods=['GET'])
@login_required
def get_employee_patients(employee_id):
    """API: получить пациентов медсестры (JSON)."""
    company_id = current_user.company_id

    # Проверить что сотрудник принадлежит компании
    employee = Employee.query.filter_by(id=employee_id, company_id=company_id).first()
    if not employee:
        return jsonify([]), 404

    # Получить активные назначения
    assignments = EmployeePatientAssignment.query.filter_by(
        employee_id=employee_id,
        company_id=company_id,
        is_active=True
    ).all()

    patients = [{
        'id': a.patient.id,
        'name': a.patient.full_name,
        'pflegegrad': a.patient.pflegegrad,
        'zimmer_nr': a.patient.zimmer_nr,
        'role': a.role
    } for a in assignments]

    return jsonify(patients)


@assignments_bp.route('/api/patient/<patient_id>/nurses', methods=['GET'])
@login_required
def get_patient_nurses(patient_id):
    """API: получить медсестер пациента (JSON)."""
    company_id = current_user.company_id

    # Проверить что пациент принадлежит компании
    patient = Patient.query.filter_by(id=patient_id, company_id=company_id).first()
    if not patient:
        return jsonify([]), 404

    # Получить активные назначения
    assignments = EmployeePatientAssignment.query.filter_by(
        patient_id=patient_id,
        company_id=company_id,
        is_active=True
    ).all()

    nurses = [{
        'id': a.employee.id,
        'name': a.employee.full_name,
        'role': a.role,
        'phone': a.employee.telefon,
        'email': a.employee.email
    } for a in assignments]

    return jsonify(nurses)
