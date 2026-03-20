"""
Email sending via SendGrid.
"""
import logging
from typing import List, Optional

from flask import current_app

logger = logging.getLogger(__name__)


def send_email(
    to: str,
    subject: str,
    html_body: str,
    text_body: Optional[str] = None,
    cc: Optional[List[str]] = None,
) -> bool:
    """Send a transactional email via SendGrid. Returns True on success."""
    api_key = current_app.config.get("SENDGRID_API_KEY")
    from_email = current_app.config.get("EMAIL_FROM", "noreply@watchflow.io")

    if not api_key:
        logger.warning("SENDGRID_API_KEY not set — skipping email to %s", to)
        return False

    try:
        from sendgrid import SendGridAPIClient
        from sendgrid.helpers.mail import Content, Mail

        mail = Mail(
            from_email=from_email,
            to_emails=to,
            subject=subject,
            html_content=html_body,
        )
        if text_body:
            mail.content = [
                Content("text/plain", text_body),
                Content("text/html", html_body),
            ]
        if cc:
            for addr in cc:
                mail.add_cc(addr)

        client = SendGridAPIClient(api_key)
        response = client.send(mail)
        logger.info("Email sent to %s (status %d)", to, response.status_code)
        return response.status_code in (200, 202)
    except Exception as exc:
        logger.error("Failed to send email to %s: %s", to, exc)
        return False


def send_verification_email(email: str, token: str, username: str) -> bool:
    base_url = current_app.config.get("BASE_URL", "https://app.watchflow.io")
    verify_url = f"{base_url}/verify-email?token={token}"
    html = f"""
    <p>Hi {username},</p>
    <p>Please verify your email address by clicking the link below:</p>
    <p><a href="{verify_url}">{verify_url}</a></p>
    <p>This link expires in 48 hours.</p>
    """
    return send_email(email, "Verify your Watchflow account", html)


def send_password_reset_email(email: str, token: str) -> bool:
    base_url = current_app.config.get("BASE_URL", "https://app.watchflow.io")
    reset_url = f"{base_url}/reset-password?token={token}"
    html = f"""
    <p>A password reset was requested for your account.</p>
    <p><a href="{reset_url}">Reset your password</a></p>
    <p>This link expires in 1 hour. If you did not request this, ignore this email.</p>
    """
    return send_email(email, "Reset your Watchflow password", html)


def send_payment_receipt(
    email: str, order_ref: str, amount_dollars: float, product_name: str
) -> bool:
    html = f"""
    <p>Thank you for your purchase!</p>
    <p><strong>Order:</strong> {order_ref}<br>
    <strong>Product:</strong> {product_name}<br>
    <strong>Amount:</strong> ${amount_dollars:.2f}</p>
    <p>Your receipt is attached. Contact support if you have questions.</p>
    """
    return send_email(email, f"Receipt for order {order_ref}", html)
