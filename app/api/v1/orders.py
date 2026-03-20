from flask import g, jsonify, request

from app.api.v1 import api_v1_bp
from app.auth.utils import admin_required, login_required
from app.models.order import Order
from app.models.product import Product
from app.payments.processor import create_payment_intent, issue_refund


@api_v1_bp.route("/orders", methods=["GET"])
@login_required
def list_orders():
    page = request.args.get("page", 1, type=int)
    per_page = min(request.args.get("per_page", 20, type=int), 100)

    query = Order.query
    if g.current_user.role != "admin":
        query = query.filter_by(user_id=g.current_user.id)

    pagination = query.order_by(Order.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    return jsonify({
        "orders": [o.to_dict() for o in pagination.items],
        "total": pagination.total,
        "page": page,
        "pages": pagination.pages,
    })


@api_v1_bp.route("/orders/<int:order_id>", methods=["GET"])
@login_required
def get_order(order_id: int):
    order = Order.query.get_or_404(order_id)
    if g.current_user.role != "admin" and order.user_id != g.current_user.id:
        return jsonify({"error": "Forbidden"}), 403
    return jsonify(order.to_dict())


@api_v1_bp.route("/orders", methods=["POST"])
@login_required
def create_order():
    data = request.get_json(silent=True) or {}
    product_slug = data.get("product_slug")
    if not product_slug:
        return jsonify({"error": "product_slug is required"}), 400

    product = Product.query.filter_by(slug=product_slug, is_active=True).first()
    if not product:
        return jsonify({"error": "Product not found"}), 404

    result = create_payment_intent(
        user=g.current_user,
        amount_cents=product.price_cents,
        currency=product.currency,
        product_id=product.id,
    )
    return jsonify(result), 201


@api_v1_bp.route("/orders/<int:order_id>/refund", methods=["POST"])
@admin_required
def refund_order(order_id: int):
    order = Order.query.get_or_404(order_id)
    data = request.get_json(silent=True) or {}
    amount_cents = data.get("amount_cents")

    try:
        result = issue_refund(order, amount_cents=amount_cents)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    return jsonify(result)
