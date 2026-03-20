"""
Payment processor — wraps Stripe API calls.
All monetary values are in cents unless stated otherwise.
"""
import logging
import secrets
import string
from typing import Any, Optional

import stripe
from flask import current_app

from app import db
from app.models.audit_log import AuditLog
from app.models.order import Order
from app.models.payment import Payment
from app.models.subscription import Subscription
from app.models.user import User

logger = logging.getLogger(__name__)


def _stripe_client():
    stripe.api_key = current_app.config["STRIPE_SECRET_KEY"]
    return stripe


def generate_order_ref(length: int = 12) -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "ORD-" + "".join(secrets.choice(alphabet) for _ in range(length))


def create_stripe_customer(user: User) -> str:
    """Create a Stripe customer and store the ID on the user."""
    s = _stripe_client()
    customer = s.Customer.create(
        email=user.email,
        name=user.username,
        metadata={"user_id": str(user.id)},
    )
    user.stripe_customer_id = customer.id
    db.session.commit()
    logger.info("Created Stripe customer %s for user %d", customer.id, user.id)
    return customer.id


def ensure_stripe_customer(user: User) -> str:
    if user.stripe_customer_id:
        return user.stripe_customer_id
    return create_stripe_customer(user)


def create_payment_intent(
    user: User,
    amount_cents: int,
    currency: str = "USD",
    product_id: Optional[int] = None,
    metadata: Optional[dict] = None,
) -> dict:
    """Create a Stripe PaymentIntent and a pending Order."""
    s = _stripe_client()
    customer_id = ensure_stripe_customer(user)

    ref = generate_order_ref()
    order = Order(
        order_ref=ref,
        user_id=user.id,
        product_id=product_id,
        status=Order.STATUS_PENDING,
        amount_cents=amount_cents,
        currency=currency.upper(),
        billing_email=user.email,
    )
    db.session.add(order)
    db.session.flush()

    intent = s.PaymentIntent.create(
        amount=amount_cents,
        currency=currency.lower(),
        customer=customer_id,
        metadata={
            "order_id": str(order.id),
            "order_ref": ref,
            "user_id": str(user.id),
            **(metadata or {}),
        },
        idempotency_key=ref,  # safe to retry — same ref always produces the same intent
    )
    order.stripe_payment_intent_id = intent.id
    db.session.commit()

    AuditLog.record(
        action="payment.intent_created",
        user_id=user.id,
        resource_type="order",
        resource_id=order.id,
        new_value={"amount_cents": amount_cents, "intent_id": intent.id},
    )
    db.session.commit()

    return {"client_secret": intent.client_secret, "order_ref": ref, "order_id": order.id}


def create_subscription(
    user: User,
    price_id: str,
    trial_days: int = 0,
    coupon: Optional[str] = None,
) -> dict:
    """Create a Stripe subscription for the user."""
    s = _stripe_client()
    customer_id = ensure_stripe_customer(user)

    params: dict[str, Any] = {
        "customer": customer_id,
        "items": [{"price": price_id}],
        "metadata": {"user_id": str(user.id)},
        "expand": ["latest_invoice.payment_intent"],
    }
    if trial_days:
        params["trial_period_days"] = trial_days
    if coupon:
        params["coupon"] = coupon

    stripe_sub = s.Subscription.create(**params)
    return stripe_sub


def cancel_subscription(subscription: Subscription, immediately: bool = False) -> Subscription:
    """Cancel a subscription at period end (or immediately)."""
    s = _stripe_client()

    if immediately:
        s.Subscription.delete(subscription.stripe_subscription_id)
        subscription.status = Subscription.STATUS_CANCELED
        from datetime import datetime, timezone
        subscription.canceled_at = datetime.now(timezone.utc)
    else:
        s.Subscription.modify(
            subscription.stripe_subscription_id,
            cancel_at_period_end=True,
        )
        subscription.cancel_at_period_end = True

    db.session.commit()
    AuditLog.record(
        action="subscription.cancel",
        user_id=subscription.user_id,
        resource_type="subscription",
        resource_id=subscription.id,
        new_value={"immediately": immediately},
    )
    db.session.commit()
    return subscription


def issue_refund(
    order: Order, amount_cents: Optional[int] = None, reason: str = "requested_by_customer"
) -> dict:
    """Issue a full or partial refund."""
    s = _stripe_client()

    if not order.stripe_charge_id and not order.stripe_payment_intent_id:
        raise ValueError("Order has no Stripe charge to refund")

    refund_amount = amount_cents or order.amount_cents
    if refund_amount > (order.amount_cents - order.refunded_amount_cents):
        raise ValueError("Refund amount exceeds refundable balance")

    params = {"amount": refund_amount, "reason": reason}
    if order.stripe_charge_id:
        params["charge"] = order.stripe_charge_id
    else:
        params["payment_intent"] = order.stripe_payment_intent_id

    refund = s.Refund.create(**params)

    order.refunded_amount_cents += refund_amount
    order.status = (
        Order.STATUS_REFUNDED
        if order.refunded_amount_cents >= order.amount_cents
        else Order.STATUS_PARTIALLY_REFUNDED
    )

    payment = Payment(
        order_id=order.id,
        payment_type=Payment.TYPE_REFUND,
        amount_cents=refund_amount,
        currency=order.currency,
        stripe_charge_id=refund.id,
        status="succeeded",
    )
    db.session.add(payment)

    AuditLog.record(
        action="payment.refund",
        user_id=order.user_id,
        resource_type="order",
        resource_id=order.id,
        new_value={"refund_amount": refund_amount, "refund_id": refund.id},
    )
    db.session.commit()
    return {"refund_id": refund.id, "amount_cents": refund_amount}
