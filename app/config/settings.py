import os


class BaseConfig:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JWT_EXPIRATION_HOURS = 24
    BCRYPT_LOG_ROUNDS = 12
    RATE_LIMIT_DEFAULT = "200 per day;50 per hour"
    REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/1")
    SENTRY_DSN = os.environ.get("SENTRY_DSN", "")
    AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
    S3_BUCKET = os.environ.get("S3_BUCKET", "watchflow-uploads")
    EMAIL_FROM = os.environ.get("EMAIL_FROM", "noreply@watchflow.io")
    SENDGRID_API_KEY = os.environ.get("SENDGRID_API_KEY", "")
    STRIPE_PUBLISHABLE_KEY = os.environ.get("STRIPE_PUBLISHABLE_KEY", "")
    STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "")
    STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB


class DevelopmentConfig(BaseConfig):
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", "postgresql://localhost/watchflow_dev"
    )


class ProductionConfig(BaseConfig):
    DEBUG = False
    TESTING = False
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL")
    SQLALCHEMY_POOL_SIZE = 10
    SQLALCHEMY_MAX_OVERFLOW = 20
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    BCRYPT_LOG_ROUNDS = 13


class TestingConfig(BaseConfig):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WTF_CSRF_ENABLED = False
    SECRET_KEY = "test-secret"  # noqa: S105
    BCRYPT_LOG_ROUNDS = 4


_configs = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
}


def get_config(name: str = "development"):
    return _configs.get(name, DevelopmentConfig)
