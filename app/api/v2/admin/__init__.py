from flask import Blueprint

admin_v2_bp = Blueprint("admin_v2", __name__)

from app.api.v2.admin import dashboard  # noqa: E402, F401
