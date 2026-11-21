"""Signup, login/logout, signup lock-down, session and CSRF requirements, rate limiting."""

from app.models import Household, HouseholdMembership, User
from app.models.enums import Role
from tests.conftest import PASSWORD, fake_password, make_client, signup


def test_signup_creates_user_household_and_owner_membership(client, db):
    me = signup(client, email="Alex@Example.com", name="Alex")
    assert me["user"]["email"] == "alex@example.com"
    assert me["household"]["name"] == "Alex's Household"
    assert me["role"] == "owner"

    user = db.query(User).one()
    household = db.query(Household).one()
    membership = db.query(HouseholdMembership).one()
    assert (membership.user_id, membership.household_id, membership.role) == (
        user.id,
        household.id,
        Role.OWNER,
    )
    # The signup response logged the user in.
    assert client.get("/api/v1/auth/me").json()["user"]["id"] == user.id


def test_duplicate_email_rejected(client):
    signup(client)
    resp = client.post(
        "/api/v1/auth/signup",
        json={"email": "ALEX@example.com", "display_name": "Other", "password": PASSWORD},
    )
    assert resp.status_code == 409
    assert resp.json()["code"] == "email_taken"


def test_short_password_rejected(client):
    resp = client.post(
        "/api/v1/auth/signup",
        json={"email": "a@example.com", "display_name": "A", "password": "s" * 5},
    )
    assert resp.status_code == 422


def test_login_logout_flow(client):
    signup(client)
    client.post("/api/v1/auth/logout")
    assert client.get("/api/v1/auth/me").status_code == 401

    bad = client.post(
        "/api/v1/auth/login", json={"email": "alex@example.com", "password": fake_password()}
    )
    assert bad.status_code == 401

    ok = client.post("/api/v1/auth/login", json={"email": "alex@example.com", "password": PASSWORD})
    assert ok.status_code == 200
    assert ok.json()["role"] == "owner"
    assert client.get("/api/v1/auth/me").status_code == 200


def test_unknown_email_gets_same_error(client):
    resp = client.post(
        "/api/v1/auth/login", json={"email": "ghost@example.com", "password": fake_password()}
    )
    assert resp.status_code == 401
    assert resp.json()["code"] == "invalid_credentials"


def test_signup_disabled_after_first_user(engine, monkeypatch):
    monkeypatch.setenv("ALLOW_SIGNUP", "false")
    with make_client() as c:
        assert c.get("/api/v1/auth/config").json() == {"signup_enabled": True}
        signup(c)  # the first account is always allowed
        assert c.get("/api/v1/auth/config").json() == {"signup_enabled": False}
    with make_client() as c2:
        resp = c2.post(
            "/api/v1/auth/signup",
            json={"email": "b@example.com", "display_name": "B", "password": PASSWORD},
        )
        assert resp.status_code == 403
        assert resp.json()["code"] == "signup_disabled"


def test_protected_endpoints_need_session(client):
    for path in (
        "/api/v1/accounts",
        "/api/v1/transactions",
        "/api/v1/summary",
        "/api/v1/household",
    ):
        assert client.get(path).status_code == 401


def test_writes_require_csrf_header(engine):
    with make_client() as c:
        signup(c)
        del c.headers["X-Requested-With"]  # simulate a cross-site form post
        resp = c.post("/api/v1/accounts", json={"name": "Cash"})
        assert resp.status_code == 403
        assert resp.json()["code"] == "csrf"


def test_login_rate_limited(client):
    signup(client)
    codes = [
        client.post(
            "/api/v1/auth/login", json={"email": "alex@example.com", "password": fake_password()}
        ).status_code
        for _ in range(11)
    ]
    assert codes[-1] == 429
