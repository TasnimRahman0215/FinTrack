"""Regression tests for the second security review (findings N1-N13).

Each test pins one fix: password-hash concurrency, account ownership rules, CORS and cookie
settings, password change and session limits, connection takeover, SimpleFIN URL parsing,
the daily "Sync now" cap, secret strength and API caching.
"""

import base64
import threading
import time
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from typer.testing import CliRunner

from app.cli import app as cli_app
from app.core import security
from app.core.clock import utcnow
from app.core.config import Settings, check_runtime_settings, get_settings
from app.core.errors import ServiceBusy
from app.main import app
from app.models import Connection, HouseholdMembership, SyncRun, UserSession
from app.models.enums import Role
from app.services import sync_service
from tests.conftest import PASSWORD, fake_password, make_client


def ids(client, scope="household"):
    return {a["id"] for a in client.get("/api/v1/accounts", params={"scope": scope}).json()}


# --- N1: password hashing can't exhaust memory ---------------------------------------------------


class _SlowHasher:
    """Stands in for argon2, recording how many hashes run at the same time."""

    def __init__(self):
        self.running = 0
        self.peak = 0
        self.lock = threading.Lock()

    def verify(self, password_hash, password):
        with self.lock:
            self.running += 1
            self.peak = max(self.peak, self.running)
        time.sleep(0.05)
        with self.lock:
            self.running -= 1
        return False


def test_at_most_n_password_hashes_run_at_once(monkeypatch):
    monkeypatch.setenv("PASSWORD_HASH_CONCURRENCY", "2")
    get_settings.cache_clear()
    security.reset_hash_slots()
    hasher = _SlowHasher()
    monkeypatch.setattr(security, "_hasher", hasher)

    threads = [
        threading.Thread(target=security.verify_password, args=(None, "guess")) for _ in range(12)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert hasher.peak == 2  # 12 parallel logins, never more than 2 hashes (~128 MiB) at once


def test_a_full_hashing_queue_answers_busy_instead_of_piling_up(monkeypatch):
    monkeypatch.setenv("PASSWORD_HASH_CONCURRENCY", "1")
    get_settings.cache_clear()
    security.reset_hash_slots()
    monkeypatch.setattr(security, "HASH_WAIT_SECONDS", 0.05)
    slots = security._hash_slots()
    slots.acquire()  # someone else is hashing
    try:
        with pytest.raises(ServiceBusy):
            security.verify_password(None, "guess")
    finally:
        slots.release()


# --- N2 / N8: who may change whose account ------------------------------------------------------


@pytest.fixture
def sams_account(partner):
    partner_client, _ = partner
    resp = partner_client.post("/api/v1/accounts", json={"name": "Sam checking"})  # shared
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_household_owner_cannot_take_a_members_account(client, owner, partner, sams_account):
    partner_client, _ = partner
    acct = sams_account["id"]
    take = {"owner_user_id": owner["user"]["id"], "visibility": "private"}
    assert client.patch(f"/api/v1/accounts/{acct}", json=take).status_code == 403
    assert client.patch(f"/api/v1/accounts/{acct}", json={"is_hidden": True}).status_code == 403
    assert client.patch(f"/api/v1/accounts/{acct}", json={"kind": "savings"}).status_code == 403
    assert client.delete(f"/api/v1/accounts/{acct}").status_code == 403
    assert acct in ids(partner_client, "me")  # still Sam's, still visible to Sam

    flags = {
        a["id"]: (a["can_edit"], a["can_manage"])
        for a in client.get("/api/v1/accounts", params={"scope": "household"}).json()
    }
    assert flags[acct] == (False, False)


def test_household_owner_looks_after_a_former_members_account(
    client, owner, partner, db, sams_account
):
    _, partner_me = partner
    db.query(HouseholdMembership).filter_by(
        user_id=partner_me["user"]["id"], household_id=owner["household"]["id"]
    ).delete()
    db.commit()  # Sam left the household; the shared account stays behind

    acct = sams_account["id"]
    resp = client.patch(f"/api/v1/accounts/{acct}", json={"owner_user_id": None})
    assert resp.status_code == 200
    assert resp.json()["visibility"] == "shared"  # now a joint account


def test_only_the_household_owner_hides_or_deletes_a_joint_account(client, owner, partner):
    partner_client, _ = partner
    joint = client.post("/api/v1/accounts", json={"name": "Joint", "owner_user_id": None}).json()
    acct = joint["id"]

    hide = partner_client.patch(f"/api/v1/accounts/{acct}", json={"is_hidden": True})
    assert hide.status_code == 403
    assert partner_client.delete(f"/api/v1/accounts/{acct}").status_code == 403
    # Everyday edits are still fine, including re-sending the current hidden value.
    resp = partner_client.patch(
        f"/api/v1/accounts/{acct}", json={"kind": "savings", "is_hidden": False}
    )
    assert resp.status_code == 200
    txn = {"account_id": acct, "date": "2026-10-01", "amount_cents": -500, "description": "Rent"}
    assert partner_client.post("/api/v1/transactions", json=txn).status_code == 201

    assert client.patch(f"/api/v1/accounts/{acct}", json={"is_hidden": True}).status_code == 200
    assert client.delete(f"/api/v1/accounts/{acct}").status_code == 204


# --- N3: CORS can't be opened to every website ---------------------------------------------------


@pytest.mark.parametrize(
    "value", ["*", "https://*.example.com", "fintrack.example.com", "https://a.example/path"]
)
def test_cors_origins_must_be_exact(value):
    with pytest.raises(ValidationError, match="exact origin"):
        Settings(cors_origins=value)


def test_exact_cors_origins_are_accepted():
    s = Settings(cors_origins="https://fintrack.example.com, http://localhost:5173")
    assert s.cors_origin_list == ["https://fintrack.example.com", "http://localhost:5173"]


# --- N4: session cookie bound to one host over HTTPS ----------------------------------------------


def test_https_cookie_uses_the_host_prefix(engine, monkeypatch):
    monkeypatch.setenv("COOKIE_SECURE", "true")
    get_settings.cache_clear()
    with make_client() as c:
        resp = c.post(
            "/api/v1/auth/signup",
            json={"email": "h@example.com", "display_name": "H", "password": PASSWORD},
        )
    cookie = resp.headers["set-cookie"]
    assert cookie.startswith("__Host-fintrack_session=")
    assert "Secure" in cookie and "Path=/" in cookie and "Domain" not in cookie


def test_plain_http_keeps_the_plain_cookie_name(client):
    resp = client.post(
        "/api/v1/auth/signup",
        json={"email": "p@example.com", "display_name": "P", "password": PASSWORD},
    )
    assert resp.headers["set-cookie"].startswith("fintrack_session=")


# --- N7: password change, sign out everywhere, hard session limit --------------------------------


def test_changing_password_signs_out_other_sessions(engine, client, owner):
    new_password = fake_password()
    email = owner["user"]["email"]
    with make_client() as phone:
        assert (
            phone.post(
                "/api/v1/auth/login", json={"email": email, "password": PASSWORD}
            ).status_code
            == 200
        )

        wrong = client.post(
            "/api/v1/auth/password",
            json={"current_password": fake_password(), "new_password": new_password},
        )
        assert wrong.status_code == 400
        assert phone.get("/api/v1/auth/me").status_code == 200  # nothing changed yet

        ok = client.post(
            "/api/v1/auth/password",
            json={"current_password": PASSWORD, "new_password": new_password},
        )
        assert ok.status_code == 204
        assert client.get("/api/v1/auth/me").status_code == 200  # this session stays
        assert phone.get("/api/v1/auth/me").status_code == 401  # the other one is gone

    assert client.post("/api/v1/auth/logout").status_code == 204
    old = client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    assert old.status_code == 401
    new = client.post("/api/v1/auth/login", json={"email": email, "password": new_password})
    assert new.status_code == 200


def test_password_change_is_rate_limited(client, owner):
    body = {"current_password": fake_password(), "new_password": fake_password()}
    codes = [client.post("/api/v1/auth/password", json=body).status_code for _ in range(6)]
    assert codes == [400] * 5 + [429]


def test_sign_out_everywhere(engine, client, owner):
    with make_client() as phone:
        phone.post(
            "/api/v1/auth/login", json={"email": owner["user"]["email"], "password": PASSWORD}
        )
        assert client.post("/api/v1/auth/logout-all").status_code == 204
        assert client.get("/api/v1/auth/me").status_code == 401
        assert phone.get("/api/v1/auth/me").status_code == 401


def test_sessions_end_at_the_hard_limit_even_when_used(client, owner, db):
    session = db.query(UserSession).one()
    session.created_at = utcnow() - timedelta(days=91)  # SESSION_MAX_DAYS defaults to 90
    session.expires_at = utcnow() + timedelta(days=10)  # still "active" by the sliding rule
    db.commit()
    assert client.get("/api/v1/auth/me").status_code == 401


def test_sliding_renewal_never_passes_the_hard_limit(client, owner, db):
    session = db.query(UserSession).one()
    session.created_at = utcnow() - timedelta(days=85)
    session.expires_at = utcnow() + timedelta(days=1)  # due for renewal
    db.commit()
    assert client.get("/api/v1/auth/me").status_code == 200
    db.refresh(session)
    assert session.expires_at <= session.created_at + timedelta(days=90)


def test_cli_reset_password(engine, client, owner, db):
    new_password = fake_password()
    runner = CliRunner()
    result = runner.invoke(
        cli_app,
        ["reset-password", owner["user"]["email"]],
        input=f"{new_password}\n{new_password}\n",
    )
    assert result.exit_code == 0, result.output
    assert client.get("/api/v1/auth/me").status_code == 401  # all sessions ended
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": owner["user"]["email"], "password": new_password},
    )
    assert resp.status_code == 200

    other = fake_password()
    password_twice = f"{other}\n{other}\n"
    missing = runner.invoke(cli_app, ["reset-password", "nobody@example.com"], input=password_twice)
    assert missing.exit_code == 1


# --- N9: a demoted member's connection can still be removed -------------------------------------


def test_household_owner_takes_over_a_demoted_members_connection(client, owner, partner, db):
    partner_client, partner_me = partner
    connection = Connection(
        household_id=owner["household"]["id"],
        added_by_user_id=partner_me["user"]["id"],
        provider="simplefin",
        credentials_enc="x",
    )
    db.add(connection)
    membership = (
        db.query(HouseholdMembership)
        .filter_by(user_id=partner_me["user"]["id"], household_id=owner["household"]["id"])
        .one()
    )
    membership.role = Role.READER
    db.commit()

    assert partner_client.delete(f"/api/v1/connections/{connection.id}").status_code == 403
    assert client.delete(f"/api/v1/connections/{connection.id}").status_code == 204


# --- N10: malformed setup tokens get a clear error, not a crash ---------------------------------


@pytest.mark.parametrize(
    "url",
    [
        "https://evil.example\t@bridge.example.com/claim",  # passes urllib, httpx refuses it
        "https://[::1]@evil.example/claim",  # urllib raises; httpx parses it, host not allowed
        "https://bridge.example.com:99999/claim",
    ],
)
def test_malformed_setup_tokens_are_a_400(client, owner, url):
    token = base64.b64encode(url.encode()).decode()
    resp = client.post("/api/v1/connections", json={"setup_token": token})
    assert resp.status_code == 400, resp.text


def test_pasted_access_url_to_another_host_is_a_400(client, owner):
    resp = client.post(
        "/api/v1/connections", json={"setup_token": "https://u:[::1]@evil.example/simplefin"}
    )
    assert resp.status_code == 400


# --- N11: "Sync now" has a daily cap per connection ---------------------------------------------


def test_manual_syncs_are_capped_per_day(db, owner, monkeypatch):
    monkeypatch.setenv("SYNC_MANUAL_DAILY_LIMIT", "3")
    get_settings.cache_clear()
    connection = Connection(
        household_id=owner["household"]["id"], provider="simplefin", credentials_enc="x"
    )
    db.add(connection)
    db.commit()
    for hours_ago in (1, 5, 20):
        db.add(
            SyncRun(
                connection_id=connection.id,
                trigger="manual",
                status="success",
                started_at=utcnow() - timedelta(hours=hours_ago),
            )
        )
    db.add(
        SyncRun(
            connection_id=connection.id,
            trigger="manual",
            status="success",
            started_at=utcnow() - timedelta(hours=30),
        )
    )  # older than a day: not counted
    db.commit()

    result = sync_service.start_household_sync(db, owner["household"]["id"])
    assert not result.started
    assert "Daily limit" in result.skipped[0].reason

    db.query(SyncRun).filter(SyncRun.started_at > utcnow() - timedelta(hours=2)).delete()
    db.commit()
    assert sync_service.start_household_sync(db, owner["household"]["id"]).started == [
        connection.id
    ]


# --- N12: a weak SECRET_KEY is refused in production ---------------------------------------------


@pytest.mark.parametrize("secret", ["changeme", "x" * 31])
def test_production_refuses_short_secrets(secret):
    with pytest.raises(RuntimeError, match="too short"):
        check_runtime_settings(Settings(environment="production", secret_key=secret))


# --- N13: API responses are never cached --------------------------------------------------------


def test_api_responses_are_not_cacheable(client, owner):
    assert client.get("/api/v1/accounts").headers["cache-control"] == "no-store"
    with make_client() as anonymous:
        assert anonymous.get("/api/v1/auth/me").headers["cache-control"] == "no-store"
    with TestClient(app) as no_csrf_header:  # blocked by the CSRF guard: still no-store
        resp = no_csrf_header.post("/api/v1/auth/logout")
        assert resp.status_code == 403 and resp.headers["cache-control"] == "no-store"
