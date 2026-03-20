"""
Tests for user management API (v1).
NOTE: Tests for v2 users API are missing — added v2 in a hurry, no coverage yet.
"""
from tests.conftest import get_auth_token


class TestGetUser:
    def test_get_own_profile(self, client, regular_user):
        token = get_auth_token(client, regular_user.email, "UserPass123!")
        resp = client.get(
            f"/api/v1/users/{regular_user.id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert resp.get_json()["email"] == regular_user.email

    def test_get_other_user_forbidden(self, client, regular_user, admin_user):
        token = get_auth_token(client, regular_user.email, "UserPass123!")
        resp = client.get(
            f"/api/v1/users/{admin_user.id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403

    def test_admin_can_get_any_user(self, client, admin_user, regular_user):
        token = get_auth_token(client, admin_user.email, "AdminPass123!")
        resp = client.get(
            f"/api/v1/users/{regular_user.id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200


class TestListUsers:
    def test_admin_can_list_users(self, client, admin_user):
        token = get_auth_token(client, admin_user.email, "AdminPass123!")
        resp = client.get("/api/v1/users", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        assert "users" in resp.get_json()

    def test_regular_user_cannot_list_users(self, client, regular_user):
        token = get_auth_token(client, regular_user.email, "UserPass123!")
        resp = client.get("/api/v1/users", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 403


# NOTE: No tests for PATCH /users/<id> or DELETE /users/<id>
# Added quickly in last sprint, didn't have time to write tests.
# Tracked: https://github.com/watchflow/watchflow/issues/441
