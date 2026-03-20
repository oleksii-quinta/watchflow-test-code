from datetime import datetime, timezone

from app import db


class Subscription(db.Model):
    __tablename__ = "subscriptions"

    STATUS_TRIALING = "trialing"
    STATUS_ACTIVE = "active"
    STATUS_PAST_DUE = "past_due"
    STATUS_CANCELED = "canceled"
    STATUS_UNPAID = "unpaid"
    STATUS_PAUSED = "paused"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    stripe_subscription_id = db.Column(db.String(64), unique=True, nullable=True, index=True)
    status = db.Column(db.String(32), nullable=False, default=STATUS_TRIALING)
    current_period_start = db.Column(db.DateTime, nullable=True)
    current_period_end = db.Column(db.DateTime, nullable=True)
    trial_start = db.Column(db.DateTime, nullable=True)
    trial_end = db.Column(db.DateTime, nullable=True)
    canceled_at = db.Column(db.DateTime, nullable=True)
    cancel_at_period_end = db.Column(db.Boolean, default=False, nullable=False)
    seats = db.Column(db.Integer, default=1, nullable=False)
    coupon_code = db.Column(db.String(64), nullable=True)
    discount_percent = db.Column(db.Integer, default=0, nullable=False)
    metadata_ = db.Column("metadata", db.JSON, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    user = db.relationship("User", back_populates="subscriptions")
    product = db.relationship("Product", back_populates="subscriptions")

    @property
    def is_active(self) -> bool:
        return self.status in (self.STATUS_ACTIVE, self.STATUS_TRIALING)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "status": self.status,
            "current_period_end": (
                self.current_period_end.isoformat() if self.current_period_end else None
            ),
            "cancel_at_period_end": self.cancel_at_period_end,
            "seats": self.seats,
        }

    def __repr__(self) -> str:
        return f"<Subscription {self.id} {self.status}>"
