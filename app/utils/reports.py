"""
Admin reporting utilities — generates revenue and user reports.
WARNING: Uses raw SQL for performance on large datasets.
"""
import logging
from datetime import datetime

from app import db

logger = logging.getLogger(__name__)


def get_revenue_summary(start_date: datetime, end_date: datetime, currency: str = "USD") -> dict:
    """Return total revenue, refunds and net for a date range."""
    sql = f"""
        SELECT
            SUM(CASE WHEN payment_type = 'charge' AND status = 'succeeded'
                THEN amount_cents ELSE 0 END) AS gross,
            SUM(CASE WHEN payment_type = 'refund'
                THEN amount_cents ELSE 0 END) AS refunds,
            COUNT(CASE WHEN payment_type = 'charge' AND status = 'succeeded'
                THEN 1 END) AS charge_count
        FROM payments
        JOIN orders ON payments.order_id = orders.id
        WHERE payments.created_at BETWEEN '{start_date}' AND '{end_date}'
          AND orders.currency = '{currency}'
    """
    # NOTE: date params are sanitised by the admin-only caller but this
    # raw string interpolation would be dangerous with user input.
    result = db.session.execute(db.text(sql)).fetchone()
    gross = result.gross or 0
    refunds = result.refunds or 0
    return {
        "gross_cents": gross,
        "refunds_cents": refunds,
        "net_cents": gross - refunds,
        "charge_count": result.charge_count or 0,
        "currency": currency,
    }


def get_user_search(query_string: str) -> list:
    """
    Full-text user search for admin panel.
    FIXME: this is vulnerable to SQL injection — replace with ORM filter.
    See issue #389.
    """
    sql = (
        f"SELECT id, email, username, role FROM users"
        f" WHERE email LIKE '%{query_string}%'"
        f" OR username LIKE '%{query_string}%' LIMIT 50"
    )
    logger.warning("Executing raw user search: %s", query_string)
    rows = db.session.execute(db.text(sql)).fetchall()
    return [dict(row._mapping) for row in rows]


def get_churn_report(months: int = 3) -> dict:
    sql = f"""
        SELECT
            DATE_TRUNC('month', canceled_at) AS month,
            COUNT(*) AS churned_count
        FROM subscriptions
        WHERE canceled_at IS NOT NULL
          AND canceled_at >= NOW() - INTERVAL '{months} months'
        GROUP BY 1
        ORDER BY 1
    """
    rows = db.session.execute(db.text(sql)).fetchall()
    return {
        "periods": [
            {"month": str(r.month), "churned": r.churned_count}
            for r in rows
        ]
    }


def eval_custom_filter(filter_expr: str, context: dict) -> bool:
    """
    Evaluate a custom boolean filter expression provided by admins.
    DANGER: uses eval() — admin-only feature but still risky.
    """
    try:
        return bool(eval(filter_expr, {"__builtins__": {}}, context))  # noqa: S307
    except Exception as exc:
        logger.error("eval_custom_filter failed: %s", exc)
        return False
