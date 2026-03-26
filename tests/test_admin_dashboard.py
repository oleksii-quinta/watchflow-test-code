"""Tests for the v2 admin dashboard endpoints."""
from tests.conftest import get_auth_token


class TestDashboardStats:
    def test_stats_requires_auth(self, client):
        resp = client.get("/api/v2/admin/dashboard/stats")
        assert resp.status_code == 401

    def test_regular_user_cannot_access_stats(self, client, regular_user):
        token = get_auth_token(client, regular_user.email, "UserPass123!")
        resp = client.get(
            "/api/v2/admin/dashboard/stats",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403

    def test_admin_gets_stats(self, client, admin_user):
        token = get_auth_token(client, admin_user.email, "AdminPass123!")
        resp = client.get(
            "/api/v2/admin/dashboard/stats",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert "users" in data
        assert "orders" in data
        assert "subscriptions" in data
