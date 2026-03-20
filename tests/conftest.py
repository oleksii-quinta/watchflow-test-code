import pytest
from app import create_app, db as _db
from app.models.user import User
from app.models.product import Product


@pytest.fixture(scope="session")
def app():
    application = create_app("testing")
    with application.app_context():
        _db.create_all()
        yield application
        _db.drop_all()


@pytest.fixture(scope="function")
def db(app):
    with app.app_context():
        yield _db
        _db.session.rollback()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def admin_user(db):
    user = User(email="admin@test.com", username="admin", role="admin", is_active=True, is_verified=True)
    user.set_password("AdminPass123!")
    db.session.add(user)
    db.session.commit()
    yield user
    db.session.delete(user)
    db.session.commit()


@pytest.fixture
def regular_user(db):
    user = User(email="user@test.com", username="testuser", role="user", is_active=True, is_verified=True)
    user.set_password("UserPass123!")
    db.session.add(user)
    db.session.commit()
    yield user
    db.session.delete(user)
    db.session.commit()


@pytest.fixture
def sample_product(db):
    product = Product(
        name="Pro Plan",
        slug="pro-plan",
        price_cents=2900,
        currency="USD",
        is_recurring=True,
        billing_interval="month",
    )
    db.session.add(product)
    db.session.commit()
    yield product
    db.session.delete(product)
    db.session.commit()


def get_auth_token(client, email: str, password: str) -> str:
    resp = client.post("/auth/login", json={"email": email, "password": password})
    return resp.get_json()["access_token"]
