from datetime import datetime, timezone
from app import db


class Order(db.Model):
    __tablename__ = "orders"

    STATUS_PENDING = "pending"
    STATUS_PAID = "paid"
    STATUS_FAILED = "failed"
    STATUS_REFUNDED = "refunded"
    STATUS_PARTIALLY_REFUNDED = "partially_refunded"
    STATUS_DISPUTED = "disputed"

    id = db.Column(db.Integer, primary_key=True)
    order_ref = db.Column(db.String(32), unique=True, nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    status = db.Column(db.String(32), nullable=False, default=STATUS_PENDING)
    amount_cents = db.Column(db.Integer, nullable=False)
    currency = db.Column(db.String(3), nullable=False, default="USD")
    stripe_payment_intent_id = db.Column(db.String(64), nullable=True, index=True)
    stripe_charge_id = db.Column(db.String(64), nullable=True)
    refunded_amount_cents = db.Column(db.Integer, default=0, nullable=False)
    billing_name = db.Column(db.String(255), nullable=True)
    billing_email = db.Column(db.String(255), nullable=True)
    billing_address = db.Column(db.JSON, nullable=True)
    ip_address = db.Column(db.String(45), nullable=True)
    user_agent = db.Column(db.String(512), nullable=True)
    metadata_ = db.Column("metadata", db.JSON, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    user = db.relationship("User", back_populates="orders")
    product = db.relationship("Product", back_populates="orders")
    payments = db.relationship("Payment", back_populates="order", lazy="dynamic")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "order_ref": self.order_ref,
            "status": self.status,
            "amount_cents": self.amount_cents,
            "currency": self.currency,
            "created_at": self.created_at.isoformat(),
        }

    def __repr__(self) -> str:
        return f"<Order {self.order_ref} {self.status}>"
