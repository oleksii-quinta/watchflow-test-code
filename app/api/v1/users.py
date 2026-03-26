from flask import g, jsonify, request

from app import db
from app.api.v1 import api_v1_bp
from app.auth.utils import admin_required, login_required
from app.models.user import User


@api_v1_bp.route("/users", methods=["GET"])
@admin_required
def list_users():
    page = request.args.get("page", 1, type=int)
    per_page = min(request.args.get("per_page", 20, type=int), 100)
    query = User.query.filter_by(deleted_at=None)

    role = request.args.get("role")
    if role:
        query = query.filter_by(role=role)

    pagination = query.order_by(User.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    return jsonify({
        "users": [u.to_dict() for u in pagination.items],
        "total": pagination.total,
        "page": page,
        "per_page": per_page,
        "pages": pagination.pages,
    })


@api_v1_bp.route("/users/<int:user_id>", methods=["GET"])
@login_required
def get_user(user_id: int):
    user = User.query.get_or_404(user_id)
    # Users can only fetch their own profile unless admin
    if g.current_user.role != "admin" and g.current_user.id != user_id:
        return jsonify({"error": "Forbidden"}), 403
    return jsonify(user.to_dict())


@api_v1_bp.route("/users/<int:user_id>", methods=["PATCH"])
@login_required
def update_user(user_id: int):
    user = User.query.get_or_404(user_id)
    if g.current_user.role != "admin" and g.current_user.id != user_id:
        return jsonify({"error": "Forbidden"}), 403

    data = request.get_json(silent=True) or {}
    allowed = {"username"}
    if g.current_user.role == "admin":
        allowed |= {"role", "is_active"}

    for field in allowed:
        if field in data:
            setattr(user, field, data[field])

    db.session.commit()
    return jsonify(user.to_dict())


@api_v1_bp.route("/users/<int:user_id>", methods=["DELETE"])
@admin_required
def delete_user(user_id: int):
    from datetime import datetime, timezone
    user = User.query.get_or_404(user_id)
    user.deleted_at = datetime.now(timezone.utc)
    db.session.commit()
    return jsonify({"message": "User deleted"}), 200


@api_v1_bp.route("/users/bulk-delete", methods=["POST"])
@admin_required
def bulk_delete_users():
    """Bulk soft-delete multiple users by ID list."""
    from datetime import datetime, timezone
    data = request.get_json(silent=True) or {}
    user_ids = data.get("user_ids", [])
    if not user_ids:
        return jsonify({"error": "user_ids list is required"}), 400

    now = datetime.now(timezone.utc)
    updated = (
        User.query.filter(User.id.in_(user_ids), User.deleted_at.is_(None))
        .update({"deleted_at": now}, synchronize_session=False)
    )
    db.session.commit()
    return jsonify({"deleted_count": updated}), 200
