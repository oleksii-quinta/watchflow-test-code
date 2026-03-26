"""
Admin dashboard endpoints — summary platform metrics for the admin panel.
Owned by the admin API team (@oleksii-quinta-3, @oleksii-quinta-4).
"""
from flask import jsonify

from app.api.v2.admin import admin_v2_bp
from app.auth.utils import admin_required
from app.models.order import Order
from app.models.subscription import Subscription
from app.models.user import User


@admin_v2_bp.route("/admin/dashboard/stats", methods=["GET"])
@admin_required
def get_dashboard_stats():
    """Return basic platform statistics for the admin dashboard."""
    total_users = User.query.filter_by(deleted_at=None).count()
    active_users = User.query.filter_by(deleted_at=None, is_active=True).count()
    total_orders = Order.query.count()
    active_subscriptions = Subscription.query.filter_by(
        status=Subscription.STATUS_ACTIVE
    ).count()

    return jsonify({
        "users": {
            "total": total_users,
            "active": active_users,
        },
        "orders": {
            "total": total_orders,
        },
        "subscriptions": {
            "active": active_subscriptions,
        },
    })
