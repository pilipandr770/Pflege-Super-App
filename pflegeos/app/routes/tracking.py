"""
Real-time employee location tracking with route history.
Supports GPS geolocation updates, live map dashboard, and audit logging.
"""

from flask import Blueprint, render_template, request, jsonify, current_app
from flask_login import login_required, current_user
from app.extensions import db
from app.models import Employee, EmployeeLocation, EmployeePatientAssignment, Patient
from app.utils.auth import patient_access_required, log_action
from datetime import datetime, timedelta
from sqlalchemy import and_, or_

tracking_bp = Blueprint('tracking', __name__, url_prefix='/tracking')


@tracking_bp.route('/dashboard')
@login_required
def dashboard():
    """Live route tracking dashboard with map."""
    # Only admins and supervisors can view
    if not current_user.is_admin and current_user.role not in ['ADMIN', 'PFLEGEFACHKRAFT']:
        return {'error': 'Access denied'}, 403

    employees = Employee.query.filter_by(
        company_id=current_user.company_id,
        is_active=True,
        deleted_at=None
    ).all()

    return render_template('tracking/dashboard.html', employees=employees)


@tracking_bp.route('/api/location', methods=['POST'])
@login_required
def submit_location():
    """Submit current GPS location."""
    try:
        data = request.get_json()

        if not data:
            return jsonify({'error': 'No data provided'}), 400

        geo_lat = data.get('latitude', type=float)
        geo_lng = data.get('longitude', type=float)
        geo_accuracy = data.get('accuracy', type=float)
        device_mac = data.get('device_mac', '')
        device_model = data.get('device_model', '')
        speed = data.get('speed', type=float)
        heading = data.get('heading', type=float)

        if not (geo_lat and geo_lng):
            return jsonify({'error': 'Missing coordinates'}), 400

        # Check if employee has an active location record
        location = EmployeeLocation.query.filter_by(
            company_id=current_user.company_id,
            employee_id=current_user.id,
            is_active=True
        ).first()

        if location:
            # Update existing location
            location.geo_lat = geo_lat
            location.geo_lng = geo_lng
            location.geo_accuracy = geo_accuracy
            location.device_mac = device_mac
            location.device_model = device_model
            location.speed = speed
            location.heading = heading
            location.updated_at = datetime.utcnow()
        else:
            # Create new location record
            location = EmployeeLocation(
                company_id=current_user.company_id,
                employee_id=current_user.id,
                geo_lat=geo_lat,
                geo_lng=geo_lng,
                geo_accuracy=geo_accuracy,
                device_mac=device_mac,
                device_model=device_model,
                speed=speed,
                heading=heading
            )
            db.session.add(location)

        db.session.commit()

        log_action('LOCATION_SUBMITTED', 'EmployeeLocation', location.id, new_values={
            'employee': current_user.full_name,
            'coordinates': f"{geo_lat},{geo_lng}",
            'accuracy': f"±{geo_accuracy}m" if geo_accuracy else "unknown"
        })

        return jsonify({
            'success': True,
            'location_id': location.id,
            'message': 'Location updated'
        }), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@tracking_bp.route('/api/locations', methods=['GET'])
@login_required
def get_active_locations():
    """Get all active employee locations (for dashboard)."""
    # Only admins and supervisors can view
    if not current_user.is_admin and current_user.role not in ['ADMIN', 'PFLEGEFACHKRAFT']:
        return jsonify({'error': 'Access denied'}), 403

    # Get the most recent location for each active employee in the company
    locations = db.session.query(EmployeeLocation).filter(
        EmployeeLocation.company_id == current_user.company_id,
        EmployeeLocation.is_active == True
    ).order_by(
        EmployeeLocation.employee_id,
        EmployeeLocation.created_at.desc()
    ).distinct(EmployeeLocation.employee_id).all()

    return jsonify([{
        'id': loc.id,
        'employee_id': loc.employee_id,
        'employee_name': loc.employee.full_name,
        'employee_role': loc.employee.role,
        'geo_lat': loc.geo_lat,
        'geo_lng': loc.geo_lng,
        'geo_accuracy': loc.geo_accuracy,
        'device_model': loc.device_model,
        'speed': loc.speed,
        'heading': loc.heading,
        'updated_at': loc.updated_at.isoformat(),
        'minutes_ago': int((datetime.utcnow() - loc.updated_at).total_seconds() / 60)
    } for loc in locations]), 200


@tracking_bp.route('/api/employee/<employee_id>/route')
@login_required
def get_employee_route(employee_id):
    """Get location history for a specific employee."""
    # Only admins can view other employees' routes
    if not current_user.is_admin and current_user.id != employee_id:
        return jsonify({'error': 'Access denied'}), 403

    employee = Employee.query.filter_by(
        id=employee_id,
        company_id=current_user.company_id,
        deleted_at=None
    ).first_or_404()

    # Get locations from the last 8 hours
    cutoff_time = datetime.utcnow() - timedelta(hours=8)

    locations = EmployeeLocation.query.filter_by(
        employee_id=employee_id,
        company_id=current_user.company_id
    ).filter(
        EmployeeLocation.created_at >= cutoff_time
    ).order_by(
        EmployeeLocation.created_at.asc()
    ).all()

    return jsonify({
        'employee': {
            'id': employee.id,
            'name': employee.full_name,
            'role': employee.role
        },
        'route': [{
            'lat': loc.geo_lat,
            'lng': loc.geo_lng,
            'accuracy': loc.geo_accuracy,
            'speed': loc.speed,
            'heading': loc.heading,
            'timestamp': loc.created_at.isoformat(),
            'device_model': loc.device_model
        } for loc in locations]
    }), 200


@tracking_bp.route('/api/locations/cleanup', methods=['POST'])
@login_required
def cleanup_old_locations():
    """Archive old location records (keep 30 days, deactivate older)."""
    if not current_user.is_admin:
        return jsonify({'error': 'Admin access required'}), 403

    cutoff_time = datetime.utcnow() - timedelta(days=30)

    # Deactivate locations older than 30 days
    old_locations = EmployeeLocation.query.filter(
        EmployeeLocation.company_id == current_user.company_id,
        EmployeeLocation.created_at < cutoff_time,
        EmployeeLocation.is_active == True
    ).update({'is_active': False}, synchronize_session=False)

    db.session.commit()

    return jsonify({
        'success': True,
        'archived_count': old_locations,
        'message': f'Archived {old_locations} location records older than 30 days'
    }), 200


@tracking_bp.route('/<employee_id>')
@login_required
def view_employee_route(employee_id):
    """View detailed route history for an employee."""
    # Only admins can view
    if not current_user.is_admin:
        return jsonify({'error': 'Access denied'}), 403

    employee = Employee.query.filter_by(
        id=employee_id,
        company_id=current_user.company_id,
        deleted_at=None
    ).first_or_404()

    return render_template('tracking/employee_route.html', employee=employee)
