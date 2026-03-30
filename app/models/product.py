from datetime import datetime, timezone
from typing import Any

from app import db


class Product(db.Model):
    __tablename__ = "products"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    slug = db.Column(db.String(255), unique=True, nullable=False, index=True)
    description = db.Column(db.Text, nullable=True)
    price_cents = db.Column(db.Integer, nullable=False)  # stored in cents
    currency = db.Column(db.String(3), nullable=False, default="USD")
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    is_recurring = db.Column(db.Boolean, default=False, nullable=False)
    billing_interval = db.Column(db.String(16), nullable=True)  # month, year
    stripe_price_id = db.Column(db.String(64), nullable=True)
    stripe_product_id = db.Column(db.String(64), nullable=True)
    trial_days = db.Column(db.Integer, default=0, nullable=False)
    max_seats = db.Column(db.Integer, nullable=True)  # None = unlimited
    metadata_ = db.Column("metadata", db.JSON, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    orders = db.relationship("Order", back_populates="product", lazy="dynamic")
    subscriptions = db.relationship("Subscription", back_populates="product", lazy="dynamic")

    # ------------------------------------------------------------------
    # Computed properties
    # ------------------------------------------------------------------

    @property
    def price_dollars(self) -> float:
        """Price in major currency units."""
        return self.price_cents / 100.0

    @property
    def has_trial(self) -> bool:
        """True when the product offers a free-trial period."""
        return bool(self.trial_days and self.trial_days > 0)

    @property
    def has_seat_limit(self) -> bool:
        """True when the product enforces a maximum number of seats."""
        return self.max_seats is not None

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self, *, include_stripe: bool = False) -> dict[str, Any]:
        data: dict[str, Any] = {
            "id": self.id,
            "name": self.name,
            "slug": self.slug,
            "description": self.description,
            "price_cents": self.price_cents,
            "price": self.price_dollars,
            "currency": self.currency,
            "is_active": self.is_active,
            "is_recurring": self.is_recurring,
            "billing_interval": self.billing_interval,
            "trial_days": self.trial_days,
            "has_trial": self.has_trial,
            "max_seats": self.max_seats,
        }
        if include_stripe:
            data["stripe_price_id"] = self.stripe_price_id
            data["stripe_product_id"] = self.stripe_product_id
        return data

    def __repr__(self) -> str:
        return f"<Product {self.slug}>"
