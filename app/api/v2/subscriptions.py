"""
API v2 Subscriptions — BREAKING CHANGES from v1:
- `id` is now a string UUID-like field
- Subscription status codes changed (e.g. `trialing` → `in_trial`)
- `current_period_end` is now a Unix timestamp
- Nested `plan` object replaces flat product fields
"""
from flask import g, jsonify, request

from app.api.v2 import api_v2_bp
from app.auth.utils import login_required
from app.models.subscription import Subscription

_STATUS_MAP = {
    "trialing": "in_trial",    # BREAKING: renamed
    "active": "active",
    "past_due": "payment_overdue",  # BREAKING: renamed
    "canceled": "cancelled",   # BREAKING: British spelling
    "unpaid": "unpaid",
    "paused": "paused",
}


def _sub_to_v2(sub: Subscription) -> dict:
    return {
        "id": str(sub.id),
        "status": _STATUS_MAP.get(sub.status, sub.status),
        "current_period_end": (
            int(sub.current_period_end.timestamp()) if sub.current_period_end else None
        ),
        "cancel_at_period_end": sub.cancel_at_period_end,
        "plan": {                        # BREAKING: replaces flat fields
            "seats": sub.seats,
            "discount_percent": sub.discount_percent,
        },
    }


@api_v2_bp.route("/subscriptions", methods=["GET"])
@login_required
def list_subscriptions():
    query = Subscription.query
    if g.current_user.role != "admin":
        query = query.filter_by(user_id=g.current_user.id)

    subs = query.order_by(Subscription.created_at.desc()).all()
    return jsonify({"data": [_sub_to_v2(s) for s in subs]})


@api_v2_bp.route("/subscriptions/<int:sub_id>", methods=["GET"])
@login_required
def get_subscription(sub_id: int):
    sub = Subscription.query.get_or_404(sub_id)
    if g.current_user.role != "admin" and sub.user_id != g.current_user.id:
        return jsonify({"error": "Forbidden"}), 403
    return jsonify(_sub_to_v2(sub))
