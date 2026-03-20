"""
Auth utilities: JWT generation/validation, MFA, permission checks.
"""
import functools
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from flask import current_app, g, jsonify, request

from app.models.user import User

logger = logging.getLogger(__name__)


def generate_token(user_id: int, role: str, expiry_hours: int = None) -> str:
    """Generate a signed JWT for the given user."""
    secret = current_app.config["SECRET_KEY"]
    hours = expiry_hours or current_app.config.get("JWT_EXPIRATION_HOURS", 24)
    payload = {
        "sub": user_id,
        "role": role,
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(hours=hours),
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def generate_refresh_token(user_id: int) -> str:
    secret = current_app.config["SECRET_KEY"]
    payload = {
        "sub": user_id,
        "type": "refresh",
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(days=30),
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def decode_token(token: str) -> Optional[dict]:
    """Decode and validate a JWT. Returns payload or None."""
    try:
        return jwt.decode(
            token,
            current_app.config["SECRET_KEY"],
            algorithms=["HS256"],
        )
    except jwt.ExpiredSignatureError:
        logger.debug("Token expired")
        return None
    except jwt.InvalidTokenError as exc:
        logger.debug("Invalid token: %s", exc)
        return None


def get_current_user() -> Optional[User]:
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None
    token = auth_header[7:]
    payload = decode_token(token)
    if not payload:
        return None
    return User.query.get(payload.get("sub"))


def login_required(f):
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        user = get_current_user()
        if not user or not user.is_active:
            return jsonify({"error": "Authentication required"}), 401
        if user.is_locked():
            return jsonify({"error": "Account locked"}), 403
        g.current_user = user
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        user = get_current_user()
        if not user:
            return jsonify({"error": "Authentication required"}), 401
        if user.role != "admin":
            return jsonify({"error": "Admin access required"}), 403
        g.current_user = user
        return f(*args, **kwargs)
    return decorated


def verify_totp(secret: str, code: str) -> bool:
    """Verify a TOTP code against a user's MFA secret."""
    try:
        import pyotp
        totp = pyotp.TOTP(secret)
        return totp.verify(code, valid_window=1)
    except Exception:
        return False


def check_permission(user: User, resource: str, action: str) -> bool:
    """Simple RBAC permission check."""
    permissions = {
        "admin": ["*:*"],
        "support": ["user:read", "order:read", "subscription:read"],
        "user": ["user:read_own", "order:read_own", "subscription:read_own"],
    }
    role_perms = permissions.get(user.role, [])
    return "*:*" in role_perms or f"{resource}:{action}" in role_perms
