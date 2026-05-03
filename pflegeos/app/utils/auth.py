import os
import json
import uuid
from functools import wraps
from datetime import datetime
from flask import request, current_app, g
from flask_login import current_user
from app.extensions import login_manager, db
from app.models import Employee, AuditLog


@login_manager.user_loader
def load_user(user_id):
    return Employee.query.filter_by(id=user_id, is_active=True, deleted_at=None).first()


def company_required(f):
    """Декоратор: проверяет что пользователь принадлежит компании."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.company_id:
            from flask import abort
            abort(403)
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    """Декоратор: только ADMIN."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'ADMIN':
            from flask import abort
            abort(403)
        return f(*args, **kwargs)
    return decorated


def log_action(action, entity_type, entity_id=None, old_values=None, new_values=None):
    """Записывает в audit_log."""
    try:
        entry = AuditLog(
            company_id=current_user.company_id if current_user.is_authenticated else None,
            user_id=current_user.id if current_user.is_authenticated else None,
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id) if entity_id else None,
            old_values=json.dumps(old_values, default=str) if old_values else None,
            new_values=json.dumps(new_values, default=str) if new_values else None,
            ip_address=request.remote_addr,
        )
        db.session.add(entry)
        db.session.commit()
    except Exception:
        pass  # Audit log никогда не должен ломать основной процесс


def allowed_file(filename):
    """Проверяет расширение файла."""
    allowed = current_app.config.get('ALLOWED_EXTENSIONS', {'png', 'jpg', 'jpeg', 'pdf'})
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed


def save_upload(file, subfolder='general'):
    """Сохраняет загруженный файл, возвращает путь."""
    import os
    from werkzeug.utils import secure_filename
    if file and allowed_file(file.filename):
        ext = file.filename.rsplit('.', 1)[1].lower()
        filename = f"{uuid.uuid4()}.{ext}"
        folder = os.path.join(current_app.config['UPLOAD_FOLDER'], subfolder)
        os.makedirs(folder, exist_ok=True)
        filepath = os.path.join(folder, filename)
        file.save(filepath)
        return os.path.join(subfolder, filename)
    return None
