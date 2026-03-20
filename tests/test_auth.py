"""Tests for auth endpoints."""
import pytest
from tests.conftest import get_auth_token


class TestRegister:
    def test_register_success(self, client, db):
        resp = client.post("/auth/register", json={
            "email": "new@example.com",
            "username": "newuser",
            "password": "SecurePass123!",
        })
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["user"]["email"] == "new@example.com"

    def test_register_duplicate_email(self, client, regular_user):
        resp = client.post("/auth/register", json={
            "email": regular_user.email,
            "username": "other",
            "password": "SecurePass123!",
        })
        assert resp.status_code == 409

    def test_register_short_password(self, client, db):
        resp = client.post("/auth/register", json={
            "email": "short@example.com",
            "username": "shortpw",
            "password": "abc",
        })
        assert resp.status_code == 400

    def test_register_missing_fields(self, client):
        resp = client.post("/auth/register", json={"email": "x@y.com"})
        assert resp.status_code == 400


class TestLogin:
    def test_login_success(self, client, regular_user):
        resp = client.post("/auth/login", json={
            "email": regular_user.email,
            "password": "UserPass123!",
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert "access_token" in data
        assert "refresh_token" in data

    def test_login_wrong_password(self, client, regular_user):
        resp = client.post("/auth/login", json={
            "email": regular_user.email,
            "password": "wrongpassword",
        })
        assert resp.status_code == 401

    def test_login_nonexistent_user(self, client):
        resp = client.post("/auth/login", json={
            "email": "ghost@nowhere.com",
            "password": "whatever",
        })
        assert resp.status_code == 401

    def test_login_inactive_user(self, client, db, regular_user):
        regular_user.is_active = False
        db.session.commit()
        resp = client.post("/auth/login", json={
            "email": regular_user.email,
            "password": "UserPass123!",
        })
        assert resp.status_code == 403
        regular_user.is_active = True
        db.session.commit()

    def test_account_lockout(self, client, regular_user):
        for _ in range(5):
            client.post("/auth/login", json={
                "email": regular_user.email,
                "password": "wrong",
            })
        resp = client.post("/auth/login", json={
            "email": regular_user.email,
            "password": "UserPass123!",
        })
        assert resp.status_code == 403


class TestMe:
    def test_me_authenticated(self, client, regular_user):
        token = get_auth_token(client, regular_user.email, "UserPass123!")
        resp = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        assert resp.get_json()["email"] == regular_user.email

    def test_me_unauthenticated(self, client):
        resp = client.get("/auth/me")
        assert resp.status_code == 401


class TestPasswordReset:
    def test_request_reset_always_200(self, client):
        resp = client.post("/auth/password-reset/request", json={"email": "ghost@nowhere.com"})
        assert resp.status_code == 200

    def test_confirm_reset_invalid_token(self, client):
        resp = client.post("/auth/password-reset/confirm", json={
            "token": "badtoken",
            "password": "NewPass123!",
        })
        assert resp.status_code == 400
