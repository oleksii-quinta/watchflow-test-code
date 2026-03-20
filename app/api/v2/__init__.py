from flask import Blueprint

api_v2_bp = Blueprint("api_v2", __name__)

from app.api.v2 import users, subscriptions  # noqa: E402, F401
