"""
API v2 Users — BREAKING CHANGES from v1:
- `id` field renamed to `uid` (string, not integer)
- `created_at` is now a Unix timestamp instead of ISO-8601 string
- `role` field removed; replaced by `permissions` list
- Pagination envelope changed: `total` → `count`, `pages` → `total_pages`
- DELETE returns 204 (was 200 with body)
- `username` field removed from list endpoint for privacy
"""
from flask import g, jsonify, request

from app import db
from app.api.v2 import api_v2_bp
from app.auth.utils import admin_required, login_required
from app.models.user import User

_ROLE_PERMISSIONS = {
    "admin": ["users:write", "orders:write", "subscriptions:write", "settings:write"],
    "support": ["users:read", "orders:read", "subscriptions:read"],
    "user": ["profile:read", "profile:write", "orders:read", "subscriptions:read"],
}


def _user_to_v2(user: User) -> dict:
    """v2 representation — incompatible with v1."""
    return {
        "uid": str(user.id),                           # was int `id`
        "email": user.email,
        # "username": omitted intentionally
        "permissions": _ROLE_PERMISSIONS.get(user.role, []),  # was `role` string
        "is_active": user.is_active,
        "is_verified": user.is_verified,
        "mfa_enabled": user.mfa_enabled,
        "created_at": int(user.created_at.timestamp()),  # was ISO-8601 string
    }


@api_v2_bp.route("/users", methods=["GET"])
@admin_required
def list_users():
    page = request.args.get("page", 1, type=int)
    per_page = min(request.args.get("per_page", 20, type=int), 100)

    pagination = (
        User.query.filter_by(deleted_at=None)
        .order_by(User.created_at.desc())
        .paginate(page=page, per_page=per_page, error_out=False)
    )
    return jsonify({
        "data": [_user_to_v2(u) for u in pagination.items],
        "count": pagination.total,           # was `total`
        "total_pages": pagination.pages,     # was `pages`
        "page": page,
        "per_page": per_page,
    })


@api_v2_bp.route("/users/<int:user_id>", methods=["GET"])
@login_required
def get_user(user_id: int):
    user = User.query.get_or_404(user_id)
    if g.current_user.role != "admin" and g.current_user.id != user_id:
        return jsonify({"error": "Forbidden"}), 403
    return jsonify(_user_to_v2(user))


@api_v2_bp.route("/users/<int:user_id>", methods=["PATCH"])
@login_required
def update_user(user_id: int):
    user = User.query.get_or_404(user_id)
    if g.current_user.role != "admin" and g.current_user.id != user_id:
        return jsonify({"error": "Forbidden"}), 403

    data = request.get_json(silent=True) or {}
    # v2: username updates are no longer allowed via PATCH
    allowed = set()
    if g.current_user.role == "admin":
        allowed = {"is_active"}  # role field removed, permissions managed separately

    for field in allowed:
        if field in data:
            setattr(user, field, data[field])

    db.session.commit()
    return jsonify(_user_to_v2(user))


@api_v2_bp.route("/users/<int:user_id>", methods=["DELETE"])
@admin_required
def delete_user(user_id: int):
    from datetime import datetime, timezone
    user = User.query.get_or_404(user_id)
    user.deleted_at = datetime.now(timezone.utc)
    db.session.commit()
    return "", 204  # v1 returned 200 with JSON body
