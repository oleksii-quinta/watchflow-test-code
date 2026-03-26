"""
Platform analytics utilities — computes user, order, and subscription metrics.

All monetary values are in cents.  All date parameters are Python datetime objects.
These helpers are intended for admin-facing dashboards and scheduled reports;
they are **not** called on hot paths.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from app import db

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# User analytics
# ---------------------------------------------------------------------------

def get_signup_counts(
    start_date: datetime,
    end_date: datetime,
    bucket: str = "day",
) -> list[dict]:
    """
    Return a time series of new user sign-ups bucketed by day, week, or month.

    Args:
        start_date: Inclusive lower bound.
        end_date:   Inclusive upper bound.
        bucket:     One of ``"day"``, ``"week"``, ``"month"``.

    Returns:
        A list of ``{"period": str, "count": int}`` dicts ordered by period asc.

    Raises:
        ValueError: If *bucket* is not one of the supported values.
    """
    if bucket not in ("day", "week", "month"):
        raise ValueError(f"Unsupported bucket: {bucket!r}. Use 'day', 'week', or 'month'.")

    trunc_expr = f"DATE_TRUNC('{bucket}', created_at)"
    sql = f"""
        SELECT
            {trunc_expr} AS period,
            COUNT(*) AS count
        FROM users
        WHERE created_at BETWEEN :start AND :end
        GROUP BY 1
        ORDER BY 1 ASC
    """
    rows = db.session.execute(
        db.text(sql), {"start": start_date, "end": end_date}
    ).fetchall()
    return [{"period": str(r.period), "count": r.count} for r in rows]


def get_active_user_count(reference_date: Optional[datetime] = None, window_days: int = 30) -> int:
    """
    Return the number of users who were active within *window_days* before *reference_date*.

    "Active" is defined as having at least one order or subscription event in the window.

    Args:
        reference_date: Defaults to now (UTC) if not provided.
        window_days:    Look-back window in days.

    Returns:
        Integer count of active users.
    """
    if reference_date is None:
        reference_date = datetime.now(timezone.utc)

    cutoff = reference_date - timedelta(days=window_days)
    sql = """
        SELECT COUNT(DISTINCT user_id) AS active_count
        FROM (
            SELECT user_id FROM orders WHERE created_at >= :cutoff
            UNION
            SELECT user_id FROM subscriptions WHERE created_at >= :cutoff
        ) AS activity
    """
    row = db.session.execute(db.text(sql), {"cutoff": cutoff}).fetchone()
    return row.active_count or 0


def get_retention_cohort(
    cohort_month: datetime,
    months_out: int = 6,
) -> list[dict]:
    """
    Compute month-N retention for users who signed up in *cohort_month*.

    Args:
        cohort_month: Any datetime within the cohort month (truncated to month start).
        months_out:   How many subsequent months to compute retention for.

    Returns:
        List of ``{"month_offset": int, "cohort_size": int, "retained": int,
        "retention_rate": float}`` dicts.
    """
    cohort_start = cohort_month.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if cohort_start.tzinfo is None:
        cohort_start = cohort_start.replace(tzinfo=timezone.utc)
    cohort_end = (cohort_start.replace(month=cohort_start.month % 12 + 1)
                  if cohort_start.month < 12
                  else cohort_start.replace(year=cohort_start.year + 1, month=1))

    sql_cohort_size = """
        SELECT COUNT(*) AS size FROM users
        WHERE created_at >= :start AND created_at < :end
    """
    cohort_size = db.session.execute(
        db.text(sql_cohort_size), {"start": cohort_start, "end": cohort_end}
    ).fetchone().size or 0

    if cohort_size == 0:
        return []

    results = []
    for offset in range(1, months_out + 1):
        window_start = cohort_end + timedelta(days=30 * (offset - 1))
        window_end = cohort_end + timedelta(days=30 * offset)
        sql_retained = """
            SELECT COUNT(DISTINCT u.id) AS retained
            FROM users u
            JOIN orders o ON o.user_id = u.id
            WHERE u.created_at >= :cohort_start
              AND u.created_at < :cohort_end
              AND o.created_at >= :window_start
              AND o.created_at < :window_end
        """
        retained = db.session.execute(
            db.text(sql_retained),
            {
                "cohort_start": cohort_start,
                "cohort_end": cohort_end,
                "window_start": window_start,
                "window_end": window_end,
            },
        ).fetchone().retained or 0
        results.append({
            "month_offset": offset,
            "cohort_size": cohort_size,
            "retained": retained,
            "retention_rate": round(retained / cohort_size, 4) if cohort_size else 0.0,
        })
    return results


def get_user_growth_rate(periods: int = 3, bucket: str = "month") -> list[dict]:
    """
    Compute period-over-period user growth rate.

    Args:
        periods: Number of periods to look back.
        bucket:  ``"day"``, ``"week"``, or ``"month"``.

    Returns:
        List of ``{"period": str, "count": int, "growth_rate": float|None}`` dicts.
    """
    now = datetime.now(timezone.utc)
    if bucket == "month":
        delta = timedelta(days=30)
    elif bucket == "week":
        delta = timedelta(weeks=1)
    else:
        delta = timedelta(days=1)

    end = now
    start = now - delta * (periods + 1)
    rows = get_signup_counts(start, end, bucket=bucket)

    enriched = []
    for i, row in enumerate(rows):
        prev_count = rows[i - 1]["count"] if i > 0 else None
        if prev_count and prev_count > 0:
            growth = round((row["count"] - prev_count) / prev_count, 4)
        else:
            growth = None
        enriched.append({**row, "growth_rate": growth})
    return enriched


# ---------------------------------------------------------------------------
# Order analytics
# ---------------------------------------------------------------------------

def get_order_volume(
    start_date: datetime,
    end_date: datetime,
    currency: str = "USD",
    bucket: str = "day",
) -> list[dict]:
    """
    Return order volume (count and gross revenue) bucketed by time.

    Args:
        start_date: Inclusive lower bound.
        end_date:   Inclusive upper bound.
        currency:   ISO-4217 currency code (case-insensitive).
        bucket:     ``"day"``, ``"week"``, or ``"month"``.

    Returns:
        List of ``{"period": str, "order_count": int, "gross_cents": int}`` dicts.
    """
    sql = f"""
        SELECT
            DATE_TRUNC('{bucket}', created_at) AS period,
            COUNT(*) AS order_count,
            SUM(amount_cents) AS gross_cents
        FROM orders
        WHERE created_at BETWEEN :start AND :end
          AND currency = :currency
          AND status NOT IN ('cancelled', 'failed')
        GROUP BY 1
        ORDER BY 1 ASC
    """
    rows = db.session.execute(
        db.text(sql),
        {"start": start_date, "end": end_date, "currency": currency.upper()},
    ).fetchall()
    return [
        {"period": str(r.period), "order_count": r.order_count, "gross_cents": r.gross_cents or 0}
        for r in rows
    ]


def get_average_order_value(
    start_date: datetime,
    end_date: datetime,
    currency: str = "USD",
) -> dict:
    """
    Return average order value for a date range.

    Returns:
        ``{"average_cents": int, "order_count": int, "total_cents": int}``
    """
    sql = """
        SELECT
            COUNT(*) AS order_count,
            COALESCE(SUM(amount_cents), 0) AS total_cents,
            COALESCE(AVG(amount_cents), 0) AS avg_cents
        FROM orders
        WHERE created_at BETWEEN :start AND :end
          AND currency = :currency
          AND status NOT IN ('cancelled', 'failed')
    """
    row = db.session.execute(
        db.text(sql),
        {"start": start_date, "end": end_date, "currency": currency.upper()},
    ).fetchone()
    return {
        "average_cents": int(row.avg_cents or 0),
        "order_count": row.order_count or 0,
        "total_cents": row.total_cents or 0,
    }


def get_order_status_breakdown(
    start_date: datetime,
    end_date: datetime,
) -> list[dict]:
    """
    Return a breakdown of order counts by status for a date range.

    Returns:
        List of ``{"status": str, "count": int}`` dicts, ordered by count desc.
    """
    sql = """
        SELECT status, COUNT(*) AS count
        FROM orders
        WHERE created_at BETWEEN :start AND :end
        GROUP BY status
        ORDER BY count DESC
    """
    rows = db.session.execute(
        db.text(sql), {"start": start_date, "end": end_date}
    ).fetchall()
    return [{"status": r.status, "count": r.count} for r in rows]


def get_top_products_by_revenue(
    start_date: datetime,
    end_date: datetime,
    limit: int = 10,
    currency: str = "USD",
) -> list[dict]:
    """
    Return the top-N products by gross revenue in a date range.

    Args:
        start_date: Inclusive lower bound.
        end_date:   Inclusive upper bound.
        limit:      Maximum number of products to return.
        currency:   ISO-4217 currency code.

    Returns:
        List of ``{"product_id": int, "product_name": str, "order_count": int,
        "gross_cents": int}`` dicts.
    """
    if limit < 1 or limit > 100:
        raise ValueError("limit must be between 1 and 100")

    sql = """
        SELECT
            p.id AS product_id,
            p.name AS product_name,
            COUNT(o.id) AS order_count,
            SUM(o.amount_cents) AS gross_cents
        FROM orders o
        JOIN products p ON o.product_id = p.id
        WHERE o.created_at BETWEEN :start AND :end
          AND o.currency = :currency
          AND o.status NOT IN ('cancelled', 'failed')
        GROUP BY p.id, p.name
        ORDER BY gross_cents DESC
        LIMIT :limit
    """
    rows = db.session.execute(
        db.text(sql),
        {"start": start_date, "end": end_date, "currency": currency.upper(), "limit": limit},
    ).fetchall()
    return [
        {
            "product_id": r.product_id,
            "product_name": r.product_name,
            "order_count": r.order_count,
            "gross_cents": r.gross_cents or 0,
        }
        for r in rows
    ]


# ---------------------------------------------------------------------------
# Subscription analytics
# ---------------------------------------------------------------------------

def get_subscription_mrr(reference_date: Optional[datetime] = None, currency: str = "USD") -> int:
    """
    Compute Monthly Recurring Revenue (MRR) as of *reference_date*.

    Only active subscriptions are included.  Yearly plans are divided by 12.

    Args:
        reference_date: Snapshot date; defaults to now.
        currency:       ISO-4217 currency code.

    Returns:
        MRR in cents.
    """
    if reference_date is None:
        reference_date = datetime.now(timezone.utc)

    sql = """
        SELECT
            SUM(
                CASE
                    WHEN p.billing_interval = 'year'  THEN p.price_cents / 12
                    WHEN p.billing_interval = 'month' THEN p.price_cents
                    ELSE 0
                END
            ) AS mrr_cents
        FROM subscriptions s
        JOIN products p ON s.product_id = p.id
        WHERE s.status = 'active'
          AND s.created_at <= :ref_date
          AND (s.canceled_at IS NULL OR s.canceled_at > :ref_date)
          AND p.currency = :currency
    """
    row = db.session.execute(
        db.text(sql), {"ref_date": reference_date, "currency": currency.upper()}
    ).fetchone()
    return int(row.mrr_cents or 0)


def get_churn_rate(
    start_date: datetime,
    end_date: datetime,
) -> dict:
    """
    Compute subscription churn rate for a period.

    Churn rate = cancellations / subscriptions active at start of period.

    Returns:
        ``{"churned": int, "active_at_start": int, "churn_rate": float}``
    """
    sql_active = """
        SELECT COUNT(*) AS count FROM subscriptions
        WHERE status = 'active' AND created_at < :start
          AND (canceled_at IS NULL OR canceled_at >= :start)
    """
    sql_churned = """
        SELECT COUNT(*) AS count FROM subscriptions
        WHERE canceled_at BETWEEN :start AND :end
    """
    active_at_start = db.session.execute(
        db.text(sql_active), {"start": start_date}
    ).fetchone().count or 0

    churned = db.session.execute(
        db.text(sql_churned), {"start": start_date, "end": end_date}
    ).fetchone().count or 0

    churn_rate = round(churned / active_at_start, 4) if active_at_start else 0.0
    return {
        "churned": churned,
        "active_at_start": active_at_start,
        "churn_rate": churn_rate,
    }


def get_subscription_plan_distribution(
    reference_date: Optional[datetime] = None,
) -> list[dict]:
    """
    Return the distribution of active subscriptions across plans.

    Returns:
        List of ``{"product_id": int, "product_name": str, "subscriber_count": int,
        "mrr_contribution_cents": int}`` dicts, ordered by subscriber count desc.
    """
    if reference_date is None:
        reference_date = datetime.now(timezone.utc)

    sql = """
        SELECT
            p.id AS product_id,
            p.name AS product_name,
            COUNT(s.id) AS subscriber_count,
            SUM(
                CASE
                    WHEN p.billing_interval = 'year'  THEN p.price_cents / 12
                    ELSE p.price_cents
                END
            ) AS mrr_contribution_cents
        FROM subscriptions s
        JOIN products p ON s.product_id = p.id
        WHERE s.status = 'active'
          AND s.created_at <= :ref_date
          AND (s.canceled_at IS NULL OR s.canceled_at > :ref_date)
        GROUP BY p.id, p.name
        ORDER BY subscriber_count DESC
    """
    rows = db.session.execute(db.text(sql), {"ref_date": reference_date}).fetchall()
    return [
        {
            "product_id": r.product_id,
            "product_name": r.product_name,
            "subscriber_count": r.subscriber_count,
            "mrr_contribution_cents": int(r.mrr_contribution_cents or 0),
        }
        for r in rows
    ]


def get_trial_conversion_rate(
    start_date: datetime,
    end_date: datetime,
) -> dict:
    """
    Compute trial-to-paid conversion rate for subscriptions that started trials in the period.

    Returns:
        ``{"trials_started": int, "converted": int, "conversion_rate": float}``
    """
    sql_trials = """
        SELECT COUNT(*) AS count FROM subscriptions
        WHERE trial_end IS NOT NULL
          AND created_at BETWEEN :start AND :end
    """
    sql_converted = """
        SELECT COUNT(*) AS count FROM subscriptions
        WHERE trial_end IS NOT NULL
          AND created_at BETWEEN :start AND :end
          AND status = 'active'
          AND trial_end < NOW()
    """
    trials = db.session.execute(
        db.text(sql_trials), {"start": start_date, "end": end_date}
    ).fetchone().count or 0

    converted = db.session.execute(
        db.text(sql_converted), {"start": start_date, "end": end_date}
    ).fetchone().count or 0

    return {
        "trials_started": trials,
        "converted": converted,
        "conversion_rate": round(converted / trials, 4) if trials else 0.0,
    }
