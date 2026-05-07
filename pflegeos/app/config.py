import os
from datetime import timedelta


def _fix_db_url(url: str) -> str:
    """
    Render.com liefert DATABASE_URL als 'postgres://' oder 'postgresql://'.
    psycopg3 braucht 'postgresql+psycopg://'.
    """
    if not url:
        return url
    if url.startswith('postgres://'):
        return 'postgresql+psycopg://' + url[len('postgres://'):]
    if url.startswith('postgresql://'):
        return 'postgresql+psycopg://' + url[len('postgresql://'):]
    return url


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-key-aendern')
    SQLALCHEMY_DATABASE_URI = _fix_db_url(
        os.environ.get('DATABASE_URL', 'postgresql+psycopg://pflegeos:pflegeos_passwort@localhost:5432/pflegeos_db')
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    DB_SCHEMA = os.environ.get('DB_SCHEMA', 'public')
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_recycle': 300,
        'connect_args': {'options': f'-c search_path={os.environ.get("DB_SCHEMA", "public")}'},
    }

    # Uploads
    UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER', 'uploads')
    MAX_CONTENT_LENGTH = int(os.environ.get('MAX_CONTENT_LENGTH', 16 * 1024 * 1024))
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf'}

    # Session
    PERMANENT_SESSION_LIFETIME = timedelta(seconds=int(os.environ.get('PERMANENT_SESSION_LIFETIME', 28800)))
    SESSION_COOKIE_SECURE = os.environ.get('SESSION_COOKIE_SECURE', '0') == '1'
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'

    # Encryption
    ENCRYPTION_KEY = os.environ.get('ENCRYPTION_KEY', '')

    # WTF
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = 3600

    # Mail
    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 587))
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', '1') == '1'
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER', 'noreply@pflegeos.local')
    SYSTEM_URL = os.environ.get('SYSTEM_URL', '')  # falls back to request.host_url in billing

    # Anthropic
    ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY', '')

    # Stripe
    STRIPE_SECRET_KEY      = os.environ.get('STRIPE_SECRET_KEY', '')
    STRIPE_PUBLISHABLE_KEY = os.environ.get('STRIPE_PUBLISHABLE_KEY', '')
    STRIPE_WEBHOOK_SECRET  = os.environ.get('STRIPE_WEBHOOK_SECRET', '')
    STRIPE_PRICE_ID        = os.environ.get('STRIPE_PRICE_ID', '')
    STRIPE_PLAN_AMOUNT     = int(os.environ.get('STRIPE_PLAN_AMOUNT', 25000))   # 250,00 €
    STRIPE_PLAN_CURRENCY   = os.environ.get('STRIPE_PLAN_CURRENCY', 'eur')
    STRIPE_PLAN_NAME       = os.environ.get('STRIPE_PLAN_NAME', 'PflegeOS Professional')


class DevelopmentConfig(Config):
    DEBUG = True
    SESSION_COOKIE_SECURE = False


class ProductionConfig(Config):
    DEBUG = False
    SESSION_COOKIE_SECURE = True


class TestingConfig(Config):
    TESTING = True
    DEBUG = True
    # Local Docker PostgreSQL — port 5432 exposed to host
    # Override with TEST_DATABASE_URL env var if needed
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'TEST_DATABASE_URL',
        'postgresql+psycopg://pflegeos:pflegeos_passwort@localhost:5432/pflegeos_test'
    )
    SQLALCHEMY_ENGINE_OPTIONS = {'pool_pre_ping': True}
    WTF_CSRF_ENABLED = False
    SESSION_COOKIE_SECURE = False
    MAIL_SUPPRESS_SEND = True
    SECRET_KEY = 'test-secret-key'


config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}
