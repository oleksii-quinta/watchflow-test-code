from flask import jsonify, request

from app import db
from app.api.v1 import api_v1_bp
from app.auth.utils import admin_required
from app.models.product import Product


@api_v1_bp.route("/products", methods=["GET"])
def list_products():
    products = Product.query.filter_by(is_active=True).order_by(Product.name).all()
    return jsonify({"products": [p.to_dict() for p in products]})


@api_v1_bp.route("/products/<slug>", methods=["GET"])
def get_product(slug: str):
    product = Product.query.filter_by(slug=slug, is_active=True).first_or_404()
    return jsonify(product.to_dict())


@api_v1_bp.route("/products", methods=["POST"])
@admin_required
def create_product():
    data = request.get_json(silent=True) or {}
    required = ("name", "slug", "price_cents", "currency")
    for field in required:
        if not data.get(field):
            return jsonify({"error": f"'{field}' is required"}), 400

    if Product.query.filter_by(slug=data["slug"]).first():
        return jsonify({"error": "Slug already exists"}), 409

    product = Product(
        name=data["name"],
        slug=data["slug"],
        description=data.get("description"),
        price_cents=data["price_cents"],
        currency=data["currency"].upper(),
        is_recurring=data.get("is_recurring", False),
        billing_interval=data.get("billing_interval"),
        trial_days=data.get("trial_days", 0),
        stripe_price_id=data.get("stripe_price_id"),
        stripe_product_id=data.get("stripe_product_id"),
    )
    db.session.add(product)
    db.session.commit()
    return jsonify(product.to_dict()), 201


@api_v1_bp.route("/products/<int:product_id>", methods=["PATCH"])
@admin_required
def update_product(product_id: int):
    product = Product.query.get_or_404(product_id)
    data = request.get_json(silent=True) or {}
    for field in ("name", "description", "is_active", "price_cents", "trial_days"):
        if field in data:
            setattr(product, field, data[field])
    db.session.commit()
    return jsonify(product.to_dict())
