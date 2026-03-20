import logging
import re
from datetime import datetime, timezone

from flask import Blueprint, g, jsonify, request

from app import db
from app.auth.utils import (
    generate_refresh_token,
    generate_token,
    login_required,
    verify_totp,
)
from app.models.audit_log import AuditLog
from app.models.user import User

auth_bp = Blueprint("auth", __name__)
logger = logging.getLogger(__name__)

MAX_FAILED_ATTEMPTS = 5


@auth_bp.route("/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}
    email = data.get("email", "").lower().strip()
    username = data.get("username", "").strip()
    password = data.get("password", "")

    if not email or not username or not password:
        return jsonify({"error": "email, username and password are required"}), 400

    if len(password) < 8:
        return jsonify({"error": "Password must be at least 8 characters"}), 400

    if not re.search(r"[A-Z]", password):
        return jsonify({"error": "Password must contain at least one uppercase letter"}), 400

    if not re.search(r"\d", password):
        return jsonify({"error": "Password must contain at least one digit"}), 400

    if User.query.filter_by(email=email).first():
        return jsonify({"error": "Email already registered"}), 409

    if User.query.filter_by(username=username).first():
        return jsonify({"error": "Username already taken"}), 409

    user = User(email=email, username=username)
    user.set_password(password)
    _token = user.generate_verification_token()

    db.session.add(user)
    db.session.commit()

    AuditLog.record(
        action="user.register",
        user_id=user.id,
        actor_ip=request.remote_addr,
        resource_type="user",
        resource_id=user.id,
    )
    db.session.commit()

    # TODO: send verification email with token
    logger.info("User registered: %s", email)
    return jsonify({"message": "Registration successful. Check your email.", "user": user.to_dict()}), 201  # noqa: E501


@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    email = data.get("email", "").lower().strip()
    password = data.get("password", "")

    if not email or not password:
        return jsonify({"error": "email and password required"}), 400

    user = User.query.filter_by(email=email, deleted_at=None).first()

    if not user:
        return jsonify({"error": "Invalid credentials"}), 401

    if user.is_locked():
        return jsonify({"error": "Account locked. Try again later."}), 403

    if not user.check_password(password):
        user.failed_login_attempts += 1
        if user.failed_login_attempts >= MAX_FAILED_ATTEMPTS:
            from datetime import timedelta
            user.locked_until = datetime.now(timezone.utc) + timedelta(minutes=30)
            AuditLog.record(
                action="user.account_locked",
                user_id=user.id,
                actor_ip=request.remote_addr,
            )
        db.session.commit()
        return jsonify({"error": "Invalid credentials"}), 401

    if not user.is_active:
        return jsonify({"error": "Account disabled"}), 403

    if user.mfa_enabled:
        mfa_code = data.get("mfa_code")
        if not mfa_code:
            return jsonify({"mfa_required": True}), 200
        if not verify_totp(user.mfa_secret, mfa_code):
            return jsonify({"error": "Invalid MFA code"}), 401

    user.failed_login_attempts = 0
    user.locked_until = None
    user.last_login_at = datetime.now(timezone.utc)
    user.last_login_ip = request.remote_addr

    access_token = generate_token(user.id, user.role)
    refresh_token = generate_refresh_token(user.id)

    AuditLog.record(
        action="user.login",
        user_id=user.id,
        actor_ip=request.remote_addr,
        resource_type="user",
        resource_id=user.id,
    )
    db.session.commit()

    return jsonify({
        "access_token": access_token,
        "refresh_token": refresh_token,
        "user": user.to_dict(),
    })


@auth_bp.route("/logout", methods=["POST"])
@login_required
def logout():
    # Stateless JWT — client must discard tokens.
    # TODO: implement token blocklist via Redis for true server-side revocation
    AuditLog.record(
        action="user.logout",
        user_id=g.current_user.id,
        actor_ip=request.remote_addr,
    )
    db.session.commit()
    return jsonify({"message": "Logged out"}), 200


@auth_bp.route("/password-reset/request", methods=["POST"])
def request_password_reset():
    data = request.get_json(silent=True) or {}
    email = data.get("email", "").lower().strip()

    user = User.query.filter_by(email=email, deleted_at=None).first()
    if user:
        _raw_token = user.generate_password_reset_token()
        db.session.commit()
        # TODO: email raw_token to user
        logger.info("Password reset requested for %s", email)

    # Always return 200 to prevent user enumeration
    return jsonify({"message": "If the email exists, a reset link has been sent."}), 200


@auth_bp.route("/password-reset/confirm", methods=["POST"])
def confirm_password_reset():
    data = request.get_json(silent=True) or {}
    token = data.get("token", "")
    new_password = data.get("password", "")

    import hashlib
    hashed = hashlib.sha256(token.encode()).hexdigest()
    user = User.query.filter_by(password_reset_token=hashed).first()

    if not user or not user.is_password_reset_valid(token):
        return jsonify({"error": "Invalid or expired token"}), 400

    if len(new_password) < 8:
        return jsonify({"error": "Password must be at least 8 characters"}), 400

    user.set_password(new_password)
    user.password_reset_token = None
    user.password_reset_expires = None

    AuditLog.record(
        action="user.password_reset",
        user_id=user.id,
        actor_ip=request.remote_addr,
    )
    db.session.commit()
    return jsonify({"message": "Password updated successfully"}), 200


@auth_bp.route("/me", methods=["GET"])
@login_required
def me():
    return jsonify(g.current_user.to_dict())
