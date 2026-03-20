from datetime import datetime, timezone

from app import db


class Payment(db.Model):
    __tablename__ = "payments"

    TYPE_CHARGE = "charge"
    TYPE_REFUND = "refund"
    TYPE_DISPUTE = "dispute"

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("orders.id"), nullable=False, index=True)
    payment_type = db.Column(db.String(32), nullable=False, default=TYPE_CHARGE)
    amount_cents = db.Column(db.Integer, nullable=False)
    currency = db.Column(db.String(3), nullable=False, default="USD")
    stripe_event_id = db.Column(db.String(64), nullable=True, unique=True)
    stripe_charge_id = db.Column(db.String(64), nullable=True)
    status = db.Column(db.String(32), nullable=False, default="pending")
    failure_code = db.Column(db.String(64), nullable=True)
    failure_message = db.Column(db.Text, nullable=True)
    card_brand = db.Column(db.String(32), nullable=True)
    card_last4 = db.Column(db.String(4), nullable=True)
    card_exp_month = db.Column(db.Integer, nullable=True)
    card_exp_year = db.Column(db.Integer, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    order = db.relationship("Order", back_populates="payments")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "payment_type": self.payment_type,
            "amount_cents": self.amount_cents,
            "currency": self.currency,
            "status": self.status,
            "card_brand": self.card_brand,
            "card_last4": self.card_last4,
            "created_at": self.created_at.isoformat(),
        }

    def __repr__(self) -> str:
        return f"<Payment {self.id} {self.payment_type} {self.status}>"
