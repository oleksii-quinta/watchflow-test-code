from datetime import datetime, timezone
from typing import Any

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

    # ------------------------------------------------------------------
    # Computed properties
    # ------------------------------------------------------------------

    @property
    def total_amount(self) -> float:
        """Order amount in major currency units (e.g. dollars)."""
        return self.amount_cents / 100.0

    @property
    def refunded_amount(self) -> float:
        """Refunded amount in major currency units."""
        return (self.refunded_amount_cents or 0) / 100.0

    @property
    def net_amount(self) -> float:
        """Amount after refunds, in major currency units."""
        return self.total_amount - self.refunded_amount

    @property
    def is_refundable(self) -> bool:
        """True when the order can still be (partially) refunded."""
        return self.status in (
            self.STATUS_PAID,
            self.STATUS_PARTIALLY_REFUNDED,
        )

    @property
    def is_fully_refunded(self) -> bool:
        return self.status == self.STATUS_REFUNDED

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self, *, include_billing: bool = False) -> dict[str, Any]:
        data: dict[str, Any] = {
            "id": self.id,
            "order_ref": self.order_ref,
            "status": self.status,
            "amount_cents": self.amount_cents,
            "amount": self.total_amount,
            "refunded_amount": self.refunded_amount,
            "net_amount": self.net_amount,
            "currency": self.currency,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
        if include_billing:
            data["billing"] = {
                "name": self.billing_name,
                "email": self.billing_email,
                "address": self.billing_address,
            }
        return data

    def __repr__(self) -> str:
        return f"<Order {self.order_ref} {self.status}>"
