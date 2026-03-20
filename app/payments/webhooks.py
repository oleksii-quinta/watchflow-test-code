"""
Stripe webhook handler.
Each event type is idempotent — safe to replay.
"""
import logging
from datetime import datetime, timezone

import stripe
from flask import Blueprint, current_app, jsonify, request

from app import db
from app.models.audit_log import AuditLog
from app.models.order import Order
from app.models.payment import Payment
from app.models.subscription import Subscription
from app.models.user import User

webhooks_bp = Blueprint("webhooks", __name__)
logger = logging.getLogger(__name__)

_HANDLED_EVENTS = {
    "payment_intent.succeeded",
    "payment_intent.payment_failed",
    "customer.subscription.created",
    "customer.subscription.updated",
    "customer.subscription.deleted",
    "invoice.paid",
    "invoice.payment_failed",
    "charge.dispute.created",
}


@webhooks_bp.route("/stripe", methods=["POST"])
def stripe_webhook():
    payload = request.get_data(as_text=True)
    sig_header = request.headers.get("Stripe-Signature")
    webhook_secret = current_app.config.get("STRIPE_WEBHOOK_SECRET")

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
    except stripe.error.SignatureVerificationError:
        logger.warning("Invalid Stripe webhook signature")
        return jsonify({"error": "Invalid signature"}), 400
    except Exception as exc:
        logger.error("Webhook parse error: %s", exc)
        return jsonify({"error": "Bad request"}), 400

    event_type = event["type"]
    if event_type not in _HANDLED_EVENTS:
        return jsonify({"status": "ignored"}), 200

    try:
        _dispatch(event)
    except Exception as exc:
        logger.exception("Webhook handler error for %s: %s", event_type, exc)
        return jsonify({"error": "Internal error"}), 500

    return jsonify({"status": "ok"}), 200


def _dispatch(event: dict) -> None:
    handlers = {
        "payment_intent.succeeded": _handle_payment_succeeded,
        "payment_intent.payment_failed": _handle_payment_failed,
        "customer.subscription.created": _handle_subscription_created,
        "customer.subscription.updated": _handle_subscription_updated,
        "customer.subscription.deleted": _handle_subscription_deleted,
        "invoice.paid": _handle_invoice_paid,
        "invoice.payment_failed": _handle_invoice_failed,
        "charge.dispute.created": _handle_dispute,
    }
    handler = handlers.get(event["type"])
    if handler:
        handler(event["data"]["object"])


def _handle_payment_succeeded(intent: dict) -> None:
    order = Order.query.filter_by(stripe_payment_intent_id=intent["id"]).first()
    if not order:
        logger.warning("No order found for intent %s", intent["id"])
        return

    # Idempotency check
    if order.status == Order.STATUS_PAID:
        return

    order.status = Order.STATUS_PAID
    order.stripe_charge_id = intent.get("latest_charge")

    charge = intent.get("charges", {}).get("data", [{}])[0] if intent.get("charges") else {}
    card = charge.get("payment_method_details", {}).get("card", {})

    payment = Payment(
        order_id=order.id,
        payment_type=Payment.TYPE_CHARGE,
        amount_cents=intent["amount"],
        currency=intent["currency"].upper(),
        stripe_event_id=intent["id"],
        stripe_charge_id=order.stripe_charge_id,
        status="succeeded",
        card_brand=card.get("brand"),
        card_last4=card.get("last4"),
        card_exp_month=card.get("exp_month"),
        card_exp_year=card.get("exp_year"),
    )
    db.session.add(payment)

    AuditLog.record(
        action="payment.succeeded",
        user_id=order.user_id,
        resource_type="order",
        resource_id=order.id,
        new_value={"amount_cents": intent["amount"], "intent_id": intent["id"]},
    )
    db.session.commit()
    logger.info("Order %s marked as paid", order.order_ref)


def _handle_payment_failed(intent: dict) -> None:
    order = Order.query.filter_by(stripe_payment_intent_id=intent["id"]).first()
    if not order:
        return

    order.status = Order.STATUS_FAILED
    last_error = intent.get("last_payment_error", {}) or {}

    payment = Payment(
        order_id=order.id,
        payment_type=Payment.TYPE_CHARGE,
        amount_cents=intent["amount"],
        currency=intent["currency"].upper(),
        stripe_event_id=intent["id"],
        status="failed",
        failure_code=last_error.get("code"),
        failure_message=last_error.get("message"),
    )
    db.session.add(payment)
    AuditLog.record(
        action="payment.failed",
        user_id=order.user_id,
        resource_type="order",
        resource_id=order.id,
        new_value={"failure_code": last_error.get("code")},
    )
    db.session.commit()


def _handle_subscription_created(stripe_sub: dict) -> None:
    user_id = int(stripe_sub["metadata"].get("user_id", 0))
    user = User.query.get(user_id)
    if not user:
        return

    sub = Subscription(
        user_id=user_id,
        stripe_subscription_id=stripe_sub["id"],
        status=stripe_sub["status"],
        current_period_start=datetime.fromtimestamp(stripe_sub["current_period_start"], tz=timezone.utc),
        current_period_end=datetime.fromtimestamp(stripe_sub["current_period_end"], tz=timezone.utc),
        trial_end=(
            datetime.fromtimestamp(stripe_sub["trial_end"], tz=timezone.utc)
            if stripe_sub.get("trial_end")
            else None
        ),
    )
    db.session.add(sub)
    db.session.commit()


def _handle_subscription_updated(stripe_sub: dict) -> None:
    sub = Subscription.query.filter_by(stripe_subscription_id=stripe_sub["id"]).first()
    if not sub:
        return

    sub.status = stripe_sub["status"]
    sub.current_period_start = datetime.fromtimestamp(
        stripe_sub["current_period_start"], tz=timezone.utc
    )
    sub.current_period_end = datetime.fromtimestamp(
        stripe_sub["current_period_end"], tz=timezone.utc
    )
    sub.cancel_at_period_end = stripe_sub.get("cancel_at_period_end", False)
    db.session.commit()


def _handle_subscription_deleted(stripe_sub: dict) -> None:
    sub = Subscription.query.filter_by(stripe_subscription_id=stripe_sub["id"]).first()
    if not sub:
        return

    sub.status = Subscription.STATUS_CANCELED
    sub.canceled_at = datetime.now(timezone.utc)
    db.session.commit()


def _handle_invoice_paid(invoice: dict) -> None:
    logger.info("Invoice paid: %s", invoice.get("id"))


def _handle_invoice_failed(invoice: dict) -> None:
    stripe_sub_id = invoice.get("subscription")
    if stripe_sub_id:
        sub = Subscription.query.filter_by(stripe_subscription_id=stripe_sub_id).first()
        if sub:
            sub.status = Subscription.STATUS_PAST_DUE
            db.session.commit()


def _handle_dispute(charge: dict) -> None:
    stripe_charge_id = charge.get("charge")
    order = Order.query.filter_by(stripe_charge_id=stripe_charge_id).first()
    if order:
        order.status = Order.STATUS_DISPUTED
        AuditLog.record(
            action="payment.dispute",
            user_id=order.user_id,
            resource_type="order",
            resource_id=order.id,
        )
        db.session.commit()
