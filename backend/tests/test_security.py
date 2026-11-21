"""Regression tests for the security review: each test pins one fix so it can't silently regress.

Grouped by finding: login lockout, connection privacy, orphaned private accounts, account edit
permissions, SimpleFIN host checks, startup checks, input bounds, rate-limiter memory, background
"Sync now" and the cross-process sync lock.
"""

import base64
from datetime import timedelta

import httpx
import pytest
from fastapi.testclient import TestClient

from app.api.v1 import auth as auth_router
from app.core import rate_limit
from app.core.clock import utcnow
from app.core.config import INSECURE_DEFAULT_SECRET, Settings, check_runtime_settings
from app.core.errors import AppError, ProviderError
from app.models import Account, Connection, SyncRun, User
from app.models.enums import Role, Visibility
from app.providers.simplefin import client as sf_client
from app.services import connection_service, sync_service
from tests.conftest import PASSWORD, join_household, make_client, signup
from tests.test_sync import FakeProvider


def ids(client, scope="household"):
    return {a["id"] for a in client.get("/api/v1/accounts", params={"scope": scope}).json()}


# --- Login rate limits: a stranger can't lock someone else out ---------------------------------


def test_bad_logins_from_one_ip_dont_lock_out_the_real_user(client, owner, monkeypatch):
    # TestClient has no real IPs, so take the "client IP" from a test header.
    monkeypatch.setattr(auth_router, "client_ip", lambda request: request.headers["x-test-ip"])
    email = owner["user"]["email"]

    def login(ip, password):
        return client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": password},
            headers={"x-test-ip": ip},
        )

    for _ in range(10):
        assert login("203.0.113.9", "wrong-password").status_code == 401
    assert login("203.0.113.9", "wrong-password").status_code == 429  # the attacker is slowed
    assert login("198.51.100.1", PASSWORD).status_code == 200  # the owner still gets in


def test_rate_limiter_forgets_idle_keys(monkeypatch):
    clock = [1000.0]
    monkeypatch.setattr(rate_limit.time, "monotonic", lambda: clock[0])
    limiter = rate_limit.RateLimiter(max_hits=5, window_seconds=60)
    for i in range(500):
        limiter.hit(f"spoofed-{i}")
    assert len(limiter) == 500
    clock[0] += 120  # the window has passed
    limiter.hit("new")
    assert len(limiter) == 1


# --- Connections don't reveal other members' private accounts ----------------------------------


@pytest.fixture
def shared_connection(client, owner, partner, db, monkeypatch):
    """The owner connects SimpleFIN (3 accounts, all private by default); a partner exists."""
    fake = FakeProvider()
    monkeypatch.setattr("app.services.connection_service.get_provider", lambda name: fake)
    monkeypatch.setattr(sync_service, "get_provider", lambda name: fake)
    resp = client.post("/api/v1/connections", json={"setup_token": "dGVzdA=="})
    assert resp.status_code == 201, resp.text
    return db.get(Connection, resp.json()["id"])


def test_connection_details_only_cover_accounts_the_viewer_can_see(
    client, partner, db, shared_connection
):
    partner_client, _ = partner
    mine = client.get("/api/v1/connections").json()[0]
    assert mine["label"] == "American Express, Chase, Robinhood"
    assert (mine["account_count"], mine["can_manage"]) == (3, True)
    assert "Robinhood" in mine["last_error"]

    theirs = partner_client.get("/api/v1/connections").json()[0]
    assert theirs["label"] == "SimpleFIN"  # every account is the owner's private one
    assert theirs["account_count"] == 0
    assert theirs["can_manage"] is False
    assert theirs["last_error"] == connection_service.OTHERS_ERROR  # provider text names banks

    # Sharing one account makes exactly that institution visible.
    card = db.query(Account).filter_by(name="Gold Card").one()
    client.patch(f"/api/v1/accounts/{card.id}", json={"visibility": "shared"})
    theirs = partner_client.get("/api/v1/connections").json()[0]
    assert (theirs["label"], theirs["account_count"]) == ("American Express", 1)


def test_sync_history_only_for_connections_you_manage(client, partner, shared_connection):
    partner_client, _ = partner
    assert len(client.get("/api/v1/sync/runs").json()) == 1
    assert partner_client.get("/api/v1/sync/runs").json() == []


def test_only_whoever_added_a_connection_can_remove_it(client, partner, db, shared_connection):
    partner_client, _ = partner
    resp = partner_client.delete(f"/api/v1/connections/{shared_connection.id}")
    assert resp.status_code == 403
    db.expire_all()
    assert db.query(Account).count() == 3  # nothing was deleted
    assert client.delete(f"/api/v1/connections/{shared_connection.id}").status_code == 204


def test_household_owner_can_remove_a_departed_members_connection(engine, client, owner, db):
    with make_client() as c:
        member = signup(c, email="left@example.com", name="Left")
    connection = Connection(
        household_id=owner["household"]["id"],
        added_by_user_id=member["user"]["id"],  # added by someone who isn't a member here
        provider="simplefin",
        credentials_enc="x",
    )
    db.add(connection)
    db.commit()
    assert client.get("/api/v1/connections").json()[0]["can_manage"] is True
    assert client.delete(f"/api/v1/connections/{connection.id}").status_code == 204


# --- A deleted user's private accounts never become joint --------------------------------------


def test_deleted_users_private_account_stays_hidden(client, owner, partner, db):
    partner_client, partner_me = partner
    secret = partner_client.post(
        "/api/v1/accounts", json={"name": "Secret stash", "visibility": "private"}
    ).json()
    db.delete(db.get(User, partner_me["user"]["id"]))  # owner_user_id becomes NULL
    db.commit()

    for scope in ("household", "me"):
        assert secret["id"] not in ids(client, scope)
    assert client.patch(f"/api/v1/accounts/{secret['id']}", json={}).status_code == 404


def test_joint_accounts_are_always_shared(client, owner):
    acct = client.post(
        "/api/v1/accounts", json={"name": "Joint", "owner_user_id": None, "visibility": "private"}
    ).json()
    assert acct["visibility"] == "shared"
    mine = client.post("/api/v1/accounts", json={"name": "Mine", "visibility": "private"}).json()
    moved = client.patch(f"/api/v1/accounts/{mine['id']}", json={"owner_user_id": None}).json()
    assert moved["visibility"] == "shared"


# --- Who may edit an account -------------------------------------------------------------------


@pytest.fixture
def household_accounts(client, owner, partner):
    def make(c, **body):
        resp = c.post("/api/v1/accounts", json={"kind": "checking", **body})
        assert resp.status_code == 201, resp.text
        return resp.json()

    return {
        "owner_shared": make(client, name="Owner cash"),
        "joint": make(client, name="Joint savings", owner_user_id=None),
    }


def test_contributor_cannot_take_a_joint_account_away(client, partner, household_accounts):
    partner_client, partner_me = partner
    joint = household_accounts["joint"]
    resp = partner_client.patch(
        f"/api/v1/accounts/{joint['id']}",
        json={"owner_user_id": partner_me["user"]["id"], "visibility": "private"},
    )
    assert resp.status_code == 403
    assert joint["id"] in ids(client)
    # ...but can still edit everyday details of a joint account.
    resp = partner_client.patch(f"/api/v1/accounts/{joint['id']}", json={"kind": "savings"})
    assert resp.status_code == 200


def test_contributor_cannot_edit_someone_elses_account(client, partner, household_accounts):
    partner_client, _ = partner
    acct = household_accounts["owner_shared"]["id"]
    assert partner_client.patch(
        f"/api/v1/accounts/{acct}", json={"is_hidden": True}
    ).status_code == (403)
    assert partner_client.delete(f"/api/v1/accounts/{acct}").status_code == 403
    txn = {"account_id": acct, "date": "2026-10-01", "amount_cents": -100, "description": "x"}
    assert partner_client.post("/api/v1/transactions", json=txn).status_code == 403

    # The owner's own transaction in that account isn't editable by the partner either.
    created = client.post("/api/v1/transactions", json=txn).json()
    assert created["editable"] is True
    listed = partner_client.get("/api/v1/transactions", params={"scope": "household"}).json()
    assert [t["editable"] for t in listed["items"]] == [False]
    resp = partner_client.patch(f"/api/v1/transactions/{created['id']}", json={"notes": "mine"})
    assert resp.status_code == 403


def test_contributor_cannot_create_an_account_for_someone_else(client, owner, partner):
    partner_client, _ = partner
    resp = partner_client.post(
        "/api/v1/accounts", json={"name": "Not yours", "owner_user_id": owner["user"]["id"]}
    )
    assert resp.status_code == 403


def test_permission_flags_match_the_rules(engine, client, owner, partner, db, household_accounts):
    partner_client, _ = partner
    flags = {
        a["name"]: (a["can_edit"], a["can_manage"])
        for a in partner_client.get("/api/v1/accounts", params={"scope": "household"}).json()
    }
    assert flags == {"Owner cash": (False, False), "Joint savings": (True, False)}

    owner_flags = {
        a["name"]: (a["can_edit"], a["can_manage"])
        for a in client.get("/api/v1/accounts", params={"scope": "household"}).json()
    }
    assert owner_flags == {"Owner cash": (True, True), "Joint savings": (True, True)}

    with make_client() as reader_client:
        reader = signup(reader_client, email="kid@example.com", name="Kid")
        join_household(
            db,
            user_id=reader["user"]["id"],
            household_id=owner["household"]["id"],
            role=Role.READER,
        )
        accounts = reader_client.get("/api/v1/accounts", params={"scope": "household"}).json()
        assert all(not a["can_edit"] and not a["can_manage"] for a in accounts)


# --- SimpleFIN: only allowed hosts are ever contacted ------------------------------------------


def _token(url: str) -> str:
    return base64.b64encode(url.encode()).decode()


@pytest.mark.parametrize(
    "url",
    [
        "https://10.0.0.5:9200/_cluster",
        "https://internal-admin.lan/claim",
        "https://bridge.simplefin.org.attacker.net/claim",  # lookalike suffix
        "https://evilsimplefin.org/claim",  # not a subdomain
        "https://bridge.simplefin.org:8443/claim",  # non-default port
    ],
)
def test_setup_tokens_for_other_hosts_are_rejected(url):
    with pytest.raises(AppError) as exc:
        sf_client.decode_setup_token(_token(url))
    assert exc.value.code == "host_not_allowed"


def test_pasted_access_urls_for_other_hosts_are_rejected():
    calls = []
    http = httpx.Client(transport=httpx.MockTransport(lambda r: calls.append(r)))
    with pytest.raises(AppError, match="only connects to SimpleFIN"):
        sf_client.claim_access_url("https://u:p@internal-admin.lan:8443/x", client=http)
    with pytest.raises(AppError, match="only connects to SimpleFIN"):
        sf_client.fetch_accounts("https://u:p@169.254.169.254/latest", client=http)
    assert calls == []  # rejected before any request


def test_real_simplefin_hosts_are_allowed():
    url = "https://beta-bridge.simplefin.org/simplefin/claim/abc"
    assert sf_client.decode_setup_token(_token(url)) == url
    base, auth = sf_client.split_access_url("https://demo:demo@beta-bridge.simplefin.org/simplefin")
    assert base == "https://beta-bridge.simplefin.org/simplefin" and auth == ("demo", "demo")


def test_claim_returning_another_host_is_rejected():
    http = httpx.Client(
        transport=httpx.MockTransport(lambda r: httpx.Response(200, text="https://u:p@evil.test/x"))
    )
    with pytest.raises(AppError, match="only connects to SimpleFIN"):
        sf_client.claim_access_url(_token("https://bridge.example.com/claim/x"), client=http)


def test_network_errors_dont_reach_users():
    def boom(request):
        raise httpx.ConnectError("[Errno 111] Connection refused to 10.1.2.3:443")

    http = httpx.Client(transport=httpx.MockTransport(boom))
    with pytest.raises(ProviderError) as exc:
        sf_client.fetch_accounts("https://u:p@bridge.example.com/simplefin", client=http)
    assert exc.value.message == sf_client.UNREACHABLE
    assert "10.1.2.3" not in exc.value.message


# --- Startup checks and API docs in production -------------------------------------------------


def test_production_refuses_the_default_secret():
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        check_runtime_settings(Settings(environment="production", secret_key=""))
    check_runtime_settings(Settings(environment="production", secret_key="x" * 64))
    check_runtime_settings(Settings(environment="development", secret_key=INSECURE_DEFAULT_SECRET))


def test_api_docs_are_off_in_production(engine, monkeypatch):
    from app.core.config import get_settings
    from app.main import create_app

    monkeypatch.setenv("ENVIRONMENT", "production")
    get_settings.cache_clear()
    with TestClient(create_app()) as c:
        assert c.get("/api/docs").status_code == 404
        assert c.get("/api/openapi.json").status_code == 404
        assert c.get("/api/v1/health").status_code == 200


# --- Money inputs are bounded ------------------------------------------------------------------


def test_huge_amounts_are_rejected_not_crashing(client, owner):
    resp = client.post("/api/v1/accounts", json={"name": "Big", "opening_balance_cents": 10**20})
    assert resp.status_code == 422
    cash = client.post("/api/v1/accounts", json={"name": "Cash"}).json()
    resp = client.patch(f"/api/v1/accounts/{cash['id']}", json={"opening_balance_cents": -(10**19)})
    assert resp.status_code == 422
    txn = {
        "account_id": cash["id"],
        "date": "2026-10-01",
        "amount_cents": 10**14,
        "description": "x",
    }
    assert client.post("/api/v1/transactions", json=txn).status_code == 422


# --- "Sync now" runs in the background; syncs are locked across processes ----------------------


def test_sync_now_returns_immediately_and_syncs_in_background(client, owner, db, monkeypatch):
    monkeypatch.setattr(sync_service, "get_provider", lambda name: FakeProvider())
    connection = Connection(
        household_id=owner["household"]["id"],
        added_by_user_id=owner["user"]["id"],
        provider="simplefin",
        credentials_enc="unused-by-fake",
    )
    db.add(connection)
    db.commit()

    resp = client.post("/api/v1/sync")
    assert resp.status_code == 202
    assert resp.json() == {"started": [connection.id], "skipped": []}
    # TestClient runs background tasks before returning, so the sync has finished by now.
    db.expire_all()
    assert db.query(SyncRun).filter_by(trigger="manual").count() == 1
    assert client.get("/api/v1/connections").json()[0]["syncing"] is False


def test_sync_lock_is_exclusive_and_expires(db, owner):
    connection = Connection(
        household_id=owner["household"]["id"], provider="simplefin", credentials_enc="x"
    )
    db.add(connection)
    db.commit()

    assert sync_service.try_claim(db, connection) is True
    assert sync_service.is_syncing(connection)
    assert sync_service.try_claim(db, connection) is False  # e.g. the worker, at the same time
    assert sync_service.sync_connection(db, connection, provider=FakeProvider()) is None

    # A claim left behind by a crashed process expires.
    connection.sync_lock_until = utcnow() - timedelta(seconds=1)
    db.commit()
    assert sync_service.try_claim(db, connection) is True


def test_new_synced_accounts_start_private(db, owner, shared_connection):
    accounts = db.query(Account).filter_by(connection_id=shared_connection.id).all()
    assert accounts and all(a.visibility == Visibility.PRIVATE for a in accounts)
