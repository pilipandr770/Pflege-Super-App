from flask import Blueprint, jsonify
from flask_login import login_required, current_user
from app.utils.email import send_bulk_missing_documentation_alerts
import logging

logger = logging.getLogger(__name__)

alerts_bp = Blueprint('alerts', __name__)


@alerts_bp.route('/check-missing-docs', methods=['POST'])
@login_required
def check_missing_docs():
    """Trigger missing documentation alerts for the company.
    Only company admins can access this endpoint."""

    # Check if user is admin
    if not current_user.is_admin:
        return jsonify({'error': 'Unauthorized'}), 403

    try:
        success = send_bulk_missing_documentation_alerts(current_user.company_id)
        if success:
            return jsonify({
                'status': 'success',
                'message': 'Missing documentation alerts queued for sending'
            }), 200
        else:
            return jsonify({
                'status': 'error',
                'message': 'Failed to send missing documentation alerts'
            }), 500
    except Exception as e:
        logger.error(f"Error triggering missing documentation alerts: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f'Error: {str(e)}'
        }), 500
