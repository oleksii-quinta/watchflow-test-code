from flask import g, jsonify, request

from app.api.v1 import api_v1_bp
from app.auth.utils import admin_required, login_required
from app.models.subscription import Subscription
from app.payments.processor import cancel_subscription, create_subscription


@api_v1_bp.route("/subscriptions", methods=["GET"])
@login_required
def list_subscriptions():
    query = Subscription.query
    if g.current_user.role != "admin":
        query = query.filter_by(user_id=g.current_user.id)

    subs = query.order_by(Subscription.created_at.desc()).all()
    return jsonify({"subscriptions": [s.to_dict() for s in subs]})


@api_v1_bp.route("/subscriptions/<int:sub_id>", methods=["GET"])
@login_required
def get_subscription(sub_id: int):
    sub = Subscription.query.get_or_404(sub_id)
    if g.current_user.role != "admin" and sub.user_id != g.current_user.id:
        return jsonify({"error": "Forbidden"}), 403
    return jsonify(sub.to_dict())


@api_v1_bp.route("/subscriptions", methods=["POST"])
@login_required
def subscribe():
    data = request.get_json(silent=True) or {}
    price_id = data.get("price_id")
    if not price_id:
        return jsonify({"error": "price_id is required"}), 400

    from app.models.product import Product
    product = Product.query.filter_by(stripe_price_id=price_id, is_active=True).first()
    if not product:
        return jsonify({"error": "Price not found"}), 404

    stripe_sub = create_subscription(
        user=g.current_user,
        price_id=price_id,
        trial_days=product.trial_days,
        coupon=data.get("coupon"),
    )
    return jsonify({"subscription_id": stripe_sub.id, "status": stripe_sub.status}), 201


@api_v1_bp.route("/subscriptions/<int:sub_id>/cancel", methods=["POST"])
@login_required
def cancel_sub(sub_id: int):
    sub = Subscription.query.get_or_404(sub_id)
    if g.current_user.role != "admin" and sub.user_id != g.current_user.id:
        return jsonify({"error": "Forbidden"}), 403

    data = request.get_json(silent=True) or {}
    immediately = data.get("immediately", False)

    if g.current_user.role != "admin":
        immediately = False  # only admins can cancel immediately

    updated = cancel_subscription(sub, immediately=immediately)
    return jsonify(updated.to_dict())
