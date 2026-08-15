import os
from flask import Flask
from dotenv import load_dotenv

load_dotenv()

from app.config import config
from app.extensions import db, login_manager, migrate, bcrypt, csrf as _csrf, mail


def create_app(config_name=None):
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'development')

    app = Flask(__name__, template_folder='templates', static_folder='static')
    app.config.from_object(config.get(config_name, config['default']))

    # Расширения
    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)
    bcrypt.init_app(app)
    _csrf.init_app(app)
    mail.init_app(app)

    # Создаём папку для загрузок
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    # Инициализируем сигналы для автоматизации
    from app.signals import init_signals
    init_signals(app)

    # Регистрируем blueprints
    from app.routes.auth import auth_bp
    from app.routes.public import public_bp
    from app.routes.dashboard import dashboard_bp
    from app.routes.patients import patients_bp
    from app.routes.sis import sis_bp
    from app.routes.medications import medications_bp
    from app.routes.leistung import leistung_bp
    from app.routes.wounds import wounds_bp
    from app.routes.company import company_bp
    from app.routes.exports import export_bp
    from app.routes.alerts import alerts_bp
    from app.routes.assignments import assignments_bp
    from app.routes.photos import photos_bp
    from app.routes.tracking import tracking_bp
    from app.routes.admin import admin_bp
    from app.routes.nurse import nurse_bp
    from app.routes.family import family_bp
    from app.routes.doctor import doctor_bp
    from app.routes.greetings import greetings_bp
    from app.routes.fuhrpark import fuhrpark_bp
    from app.routes.buchhaltung import buchhaltung_bp
    from app.routes.superadmin import superadmin_bp
    from app.routes.billing import billing_bp
    from app.routes.schichtplan import schichtplan_bp
    from app.routes.sturzprotokoll import sturzprotokoll_bp
    from app.routes.qm import qm_bp
    from app.routes.gkv import gkv_bp
    from app.routes.onboarding import onboarding_bp
    from app.routes.standorte import standorte_bp
    from app.routes.hkp import hkp_bp
    from app.routes.pflegevertrag import pflegevertrag_bp
    from app.routes.privatrechnung import privatrechnung_bp

    app.register_blueprint(public_bp)
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(dashboard_bp, url_prefix='/')
    app.register_blueprint(patients_bp, url_prefix='/patients')
    app.register_blueprint(sis_bp, url_prefix='/sis')
    app.register_blueprint(medications_bp, url_prefix='/medications')
    app.register_blueprint(leistung_bp, url_prefix='/leistung')
    app.register_blueprint(wounds_bp, url_prefix='/wounds')
    app.register_blueprint(company_bp, url_prefix='/company')
    app.register_blueprint(alerts_bp, url_prefix='/alerts')
    app.register_blueprint(assignments_bp, url_prefix='/assignments')
    app.register_blueprint(admin_bp)
    app.register_blueprint(photos_bp, url_prefix='/photos')
    app.register_blueprint(tracking_bp, url_prefix='/tracking')
    app.register_blueprint(nurse_bp, url_prefix='/nurse')
    app.register_blueprint(family_bp)
    app.register_blueprint(doctor_bp)
    app.register_blueprint(export_bp)
    app.register_blueprint(greetings_bp)
    app.register_blueprint(fuhrpark_bp, url_prefix='/fuhrpark')
    app.register_blueprint(buchhaltung_bp, url_prefix='/buchhaltung')
    app.register_blueprint(superadmin_bp, url_prefix='/superadmin')
    app.register_blueprint(billing_bp)
    app.register_blueprint(schichtplan_bp)
    app.register_blueprint(sturzprotokoll_bp)
    app.register_blueprint(qm_bp)
    app.register_blueprint(gkv_bp, url_prefix='/gkv')
    app.register_blueprint(onboarding_bp)
    app.register_blueprint(standorte_bp)
    app.register_blueprint(hkp_bp)
    app.register_blueprint(pflegevertrag_bp)
    app.register_blueprint(privatrechnung_bp)

    # Stripe Webhook muss CSRF-exempt sein (Stripe sendet kein CSRF-Token)
    _csrf.exempt(billing_bp)

    # Планировщик задач (утренняя проверка поздравлений)
    from app.tasks import init_scheduler
    init_scheduler(app)

    # Глобальные template filters
    def _fmt(value, fmt='%d.%m.%Y'):
        if value is None:
            return '—'
        return value.strftime(fmt)

    app.template_filter('datefmt')(_fmt)
    app.template_filter('dateformat')(_fmt)   # alias — некоторые шаблоны используют это имя

    @app.template_filter('datetimefmt')
    def datetimefmt(value, fmt='%d.%m.%Y %H:%M'):
        if value is None:
            return '—'
        return value.strftime(fmt)

    @app.template_filter('from_json')
    def from_json_filter(value):
        import json
        if not value:
            return {}
        try:
            return json.loads(value)
        except Exception:
            return {}

    # Globale Context-Variablen für alle Templates
    from datetime import datetime as _dt
    @app.context_processor
    def inject_globals():
        return {'now': _dt.utcnow()}

    return app
