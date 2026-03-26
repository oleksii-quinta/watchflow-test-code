"""
Unit tests for app/utils/analytics.py.

All DB calls are exercised through the real test DB (no mocking).
"""
from datetime import datetime, timedelta, timezone

import pytest

from app.utils.analytics import (
    get_active_user_count,
    get_average_order_value,
    get_churn_rate,
    get_order_status_breakdown,
    get_order_volume,
    get_retention_cohort,
    get_signup_counts,
    get_subscription_mrr,
    get_subscription_plan_distribution,
    get_top_products_by_revenue,
    get_trial_conversion_rate,
    get_user_growth_rate,
)

NOW = datetime.now(timezone.utc)
PAST = NOW - timedelta(days=90)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _assert_list_of_dicts(result, required_keys):
    assert isinstance(result, list)
    for item in result:
        for key in required_keys:
            assert key in item, f"Missing key {key!r} in {item}"


# ---------------------------------------------------------------------------
# User analytics tests
# ---------------------------------------------------------------------------

class TestGetSignupCounts:
    def test_returns_list(self, app):
        with app.app_context():
            result = get_signup_counts(PAST, NOW, bucket="day")
        assert isinstance(result, list)

    def test_each_row_has_period_and_count(self, app):
        with app.app_context():
            result = get_signup_counts(PAST, NOW, bucket="month")
        _assert_list_of_dicts(result, ["period", "count"])

    def test_invalid_bucket_raises(self, app):
        with app.app_context():
            with pytest.raises(ValueError, match="Unsupported bucket"):
                get_signup_counts(PAST, NOW, bucket="quarter")

    def test_week_bucket(self, app):
        with app.app_context():
            result = get_signup_counts(PAST, NOW, bucket="week")
        assert isinstance(result, list)

    def test_empty_range_returns_empty(self, app):
        future = NOW + timedelta(days=365)
        with app.app_context():
            result = get_signup_counts(future, future + timedelta(days=1), bucket="day")
        assert result == []


class TestGetActiveUserCount:
    def test_returns_int(self, app):
        with app.app_context():
            result = get_active_user_count()
        assert isinstance(result, int)
        assert result >= 0

    def test_custom_window(self, app):
        with app.app_context():
            result = get_active_user_count(window_days=7)
        assert isinstance(result, int)

    def test_future_reference_date(self, app):
        with app.app_context():
            result = get_active_user_count(reference_date=NOW + timedelta(days=365))
        assert isinstance(result, int)


class TestGetRetentionCohort:
    def test_returns_list(self, app):
        with app.app_context():
            result = get_retention_cohort(NOW - timedelta(days=180))
        assert isinstance(result, list)

    def test_row_structure(self, app):
        with app.app_context():
            result = get_retention_cohort(NOW - timedelta(days=180), months_out=3)
        _assert_list_of_dicts(result, ["month_offset", "cohort_size", "retained", "retention_rate"])

    def test_retention_rate_between_zero_and_one(self, app):
        with app.app_context():
            result = get_retention_cohort(NOW - timedelta(days=180))
        for row in result:
            assert 0.0 <= row["retention_rate"] <= 1.0

    def test_months_out_param(self, app):
        with app.app_context():
            result = get_retention_cohort(NOW - timedelta(days=180), months_out=2)
        assert len(result) <= 2


class TestGetUserGrowthRate:
    def test_returns_list(self, app):
        with app.app_context():
            result = get_user_growth_rate(periods=3)
        assert isinstance(result, list)

    def test_row_has_growth_rate(self, app):
        with app.app_context():
            result = get_user_growth_rate()
        for row in result:
            assert "growth_rate" in row


# ---------------------------------------------------------------------------
# Order analytics tests
# ---------------------------------------------------------------------------

class TestGetOrderVolume:
    def test_returns_list(self, app):
        with app.app_context():
            result = get_order_volume(PAST, NOW)
        assert isinstance(result, list)

    def test_row_structure(self, app):
        with app.app_context():
            result = get_order_volume(PAST, NOW, bucket="month")
        _assert_list_of_dicts(result, ["period", "order_count", "gross_cents"])

    def test_gross_cents_non_negative(self, app):
        with app.app_context():
            result = get_order_volume(PAST, NOW)
        for row in result:
            assert row["gross_cents"] >= 0


class TestGetAverageOrderValue:
    def test_returns_dict(self, app):
        with app.app_context():
            result = get_average_order_value(PAST, NOW)
        assert isinstance(result, dict)
        assert "average_cents" in result
        assert "order_count" in result
        assert "total_cents" in result

    def test_values_non_negative(self, app):
        with app.app_context():
            result = get_average_order_value(PAST, NOW)
        assert result["average_cents"] >= 0
        assert result["order_count"] >= 0
        assert result["total_cents"] >= 0


class TestGetOrderStatusBreakdown:
    def test_returns_list(self, app):
        with app.app_context():
            result = get_order_status_breakdown(PAST, NOW)
        assert isinstance(result, list)

    def test_row_structure(self, app):
        with app.app_context():
            result = get_order_status_breakdown(PAST, NOW)
        _assert_list_of_dicts(result, ["status", "count"])


class TestGetTopProductsByRevenue:
    def test_returns_list(self, app):
        with app.app_context():
            result = get_top_products_by_revenue(PAST, NOW)
        assert isinstance(result, list)

    def test_limit_respected(self, app):
        with app.app_context():
            result = get_top_products_by_revenue(PAST, NOW, limit=3)
        assert len(result) <= 3

    def test_invalid_limit_raises(self, app):
        with app.app_context():
            with pytest.raises(ValueError):
                get_top_products_by_revenue(PAST, NOW, limit=0)

    def test_row_structure(self, app):
        with app.app_context():
            result = get_top_products_by_revenue(PAST, NOW)
        _assert_list_of_dicts(result, ["product_id", "product_name", "order_count", "gross_cents"])


# ---------------------------------------------------------------------------
# Subscription analytics tests
# ---------------------------------------------------------------------------

class TestGetSubscriptionMrr:
    def test_returns_int(self, app):
        with app.app_context():
            result = get_subscription_mrr()
        assert isinstance(result, int)
        assert result >= 0

    def test_custom_reference_date(self, app):
        with app.app_context():
            result = get_subscription_mrr(reference_date=PAST)
        assert isinstance(result, int)


class TestGetChurnRate:
    def test_returns_dict(self, app):
        with app.app_context():
            result = get_churn_rate(PAST, NOW)
        assert isinstance(result, dict)
        assert "churned" in result
        assert "active_at_start" in result
        assert "churn_rate" in result

    def test_churn_rate_between_zero_and_one(self, app):
        with app.app_context():
            result = get_churn_rate(PAST, NOW)
        assert 0.0 <= result["churn_rate"] <= 1.0


class TestGetSubscriptionPlanDistribution:
    def test_returns_list(self, app):
        with app.app_context():
            result = get_subscription_plan_distribution()
        assert isinstance(result, list)

    def test_row_structure(self, app):
        with app.app_context():
            result = get_subscription_plan_distribution()
        _assert_list_of_dicts(result, ["product_id", "product_name", "subscriber_count",
                                        "mrr_contribution_cents"])


class TestGetTrialConversionRate:
    def test_returns_dict(self, app):
        with app.app_context():
            result = get_trial_conversion_rate(PAST, NOW)
        assert isinstance(result, dict)
        assert "trials_started" in result
        assert "converted" in result
        assert "conversion_rate" in result

    def test_conversion_rate_between_zero_and_one(self, app):
        with app.app_context():
            result = get_trial_conversion_rate(PAST, NOW)
        assert 0.0 <= result["conversion_rate"] <= 1.0
