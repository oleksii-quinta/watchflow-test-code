"""Tests for products API (v1)."""
from tests.conftest import get_auth_token


class TestListProducts:
    def test_list_products_public(self, client, sample_product):
        resp = client.get("/api/v1/products")
        assert resp.status_code == 200
        assert len(resp.get_json()["products"]) >= 1

    def test_get_product_by_slug(self, client, sample_product):
        resp = client.get(f"/api/v1/products/{sample_product.slug}")
        assert resp.status_code == 200
        assert resp.get_json()["slug"] == sample_product.slug

    def test_get_product_not_found(self, client):
        resp = client.get("/api/v1/products/nonexistent-slug")
        assert resp.status_code == 404


class TestCreateProduct:
    def test_create_product_as_admin(self, client, admin_user):
        token = get_auth_token(client, admin_user.email, "AdminPass123!")
        resp = client.post(
            "/api/v1/products",
            json={
                "name": "Enterprise Plan",
                "slug": "enterprise-plan",
                "price_cents": 49900,
                "currency": "USD",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 201
        assert resp.get_json()["slug"] == "enterprise-plan"

    def test_create_product_as_user_forbidden(self, client, regular_user):
        token = get_auth_token(client, regular_user.email, "UserPass123!")
        resp = client.post(
            "/api/v1/products",
            json={"name": "Hack", "slug": "hack", "price_cents": 0, "currency": "USD"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403

    def test_create_product_missing_fields(self, client, admin_user):
        token = get_auth_token(client, admin_user.email, "AdminPass123!")
        resp = client.post(
            "/api/v1/products",
            json={"name": "Incomplete"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 400
