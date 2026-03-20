from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from app.config.settings import get_config

db = SQLAlchemy()
migrate = Migrate()
limiter = Limiter(key_func=get_remote_address)


def create_app(config_name="development"):
    app = Flask(__name__)
    config = get_config(config_name)
    app.config.from_object(config)

    db.init_app(app)
    migrate.init_app(app, db)
    limiter.init_app(app)

    from app.auth.views import auth_bp
    from app.api.v1 import api_v1_bp
    from app.api.v2 import api_v2_bp
    from app.payments.webhooks import webhooks_bp

    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(api_v1_bp, url_prefix="/api/v1")
    app.register_blueprint(api_v2_bp, url_prefix="/api/v2")
    app.register_blueprint(webhooks_bp, url_prefix="/webhooks")

    return app
