"""Sync service behaviour: upserts, idempotency, pending->posted, user fields, cooldowns."""

import copy
from datetime import timedelta

import pytest

from app.core import security
from app.core.clock import to_unix, utcnow
from app.core.errors import ProviderAuthError
from app.models import Account, BalanceSnapshot, Connection, SyncRun, Transaction
from app.models.enums import AccountKind, ConnectionStatus, SyncStatus
from app.providers.base import Provider
from app.providers.simplefin.mapper import map_response
from app.services import sync_service
from tests.conftest import load_fixture


class FakeProvider(Provider):
    """Returns the fixture data (or raises `error`) and records each requested date range."""

    name = "simplefin"

    def __init__(self, data=None, error=None):
        self.data = data or load_fixture("simplefin_accounts.json")
        self.error = error
        self.calls = []

    def connect(self, setup_payload):
        return "https://u:p@bridge.example.com/simplefin", "SimpleFIN (bridge.example.com)"

    def fetch(self, credentials, start, end):
        self.calls.append((start, end))
        if self.error:
            raise self.error
        return map_response(copy.deepcopy(self.data))


@pytest.fixture
def connection(db, owner) -> Connection:
    """A saved SimpleFIN connection owned by `owner`, with dummy encrypted credentials."""
    conn = Connection(
        household_id=owner["household"]["id"],
        added_by_user_id=owner["user"]["id"],
        provider="simplefin",
        credentials_enc=security.encrypt("https://u:p@bridge.example.com/simplefin"),
    )
    db.add(conn)
    db.commit()
    return conn


def test_first_sync_creates_accounts_and_transactions(db, owner, connection):
    run = sync_service.sync_connection(db, connection, provider=FakeProvider())
    assert run.status == SyncStatus.PARTIAL  # the fixture includes a provider warning
    assert run.errors == ["Connection to Robinhood may need attention"]
    assert (run.accounts_seen, run.txns_new, run.txns_updated) == (3, 4, 0)

    accounts = {a.name: a for a in db.query(Account).all()}
    assert accounts["Total Checking"].kind == AccountKind.CHECKING
    assert accounts["Gold Card"].kind == AccountKind.CREDIT
    assert accounts["Individual"].kind == AccountKind.INVESTMENT  # org is Robinhood
    assert all(a.owner_user_id == owner["user"]["id"] for a in accounts.values())
    assert db.query(BalanceSnapshot).count() == 3
    assert connection.label == "American Express, Chase, Robinhood"
    assert connection.last_synced_at is not None


def test_sync_is_idempotent(db, connection):
    sync_service.sync_connection(db, connection, provider=FakeProvider())
    run = sync_service.sync_connection(db, connection, provider=FakeProvider())
    assert (run.txns_new, run.txns_updated, run.txns_removed) == (0, 0, 0)
    assert db.query(Transaction).count() == 4
    assert db.query(Account).count() == 3


def test_second_sync_uses_overlap_window(db, connection):
    provider = FakeProvider()
    sync_service.sync_connection(db, connection, provider=provider)
    sync_service.sync_connection(db, connection, provider=provider)
    first_start, _ = provider.calls[0]
    second_start, _ = provider.calls[1]
    assert utcnow() - first_start > timedelta(days=89)
    assert utcnow() - second_start < timedelta(days=15)


def test_pending_replaced_by_posted(db, connection):
    # Pending cleanup only applies inside the re-fetched window, so use recent dates.
    yesterday = to_unix(utcnow() - timedelta(days=1))
    data = load_fixture("simplefin_accounts.json")
    data["accounts"][0]["transactions"][2]["transacted_at"] = yesterday
    sync_service.sync_connection(db, connection, provider=FakeProvider(data))

    data = copy.deepcopy(data)
    txns = data["accounts"][0]["transactions"]
    txns[2] = {**txns[2], "id": "TRN-POSTED-1", "posted": yesterday + 3600, "pending": False}
    run = sync_service.sync_connection(db, connection, provider=FakeProvider(data))
    assert (run.txns_new, run.txns_removed) == (1, 1)
    descriptions = [t.description for t in db.query(Transaction).filter_by(pending=True)]
    assert descriptions == []


def test_user_fields_survive_resync(db, connection):
    sync_service.sync_connection(db, connection, provider=FakeProvider())
    account = db.query(Account).filter_by(name="Gold Card").one()
    account.display_name = "Amex"
    account.visibility = "private"
    txn = db.query(Transaction).filter_by(provider_txn_id="TRN-1").one()
    txn.notes = "Weekly groceries"
    db.commit()

    data = load_fixture("simplefin_accounts.json")
    data["accounts"][0]["transactions"][0]["description"] = "WHOLE FOODS MARKET"
    run = sync_service.sync_connection(db, connection, provider=FakeProvider(data))
    assert run.txns_updated == 1

    db.refresh(account)
    db.refresh(txn)
    assert (account.display_name, account.visibility) == ("Amex", "private")
    assert txn.notes == "Weekly groceries"
    assert txn.description == "WHOLE FOODS MARKET"


def test_auth_failure_marks_connection(db, connection):
    run = sync_service.sync_connection(
        db, connection, provider=FakeProvider(error=ProviderAuthError("revoked"))
    )
    assert run.status == SyncStatus.FAILED
    assert connection.status == ConnectionStatus.REAUTH_REQUIRED
    assert connection.last_error == "revoked"


def test_sync_now_respects_cooldown(db, owner, connection, monkeypatch):
    monkeypatch.setattr(sync_service, "get_provider", lambda name: FakeProvider())
    first = sync_service.sync_household(db, owner["household"]["id"])
    assert len(first.runs) == 1 and not first.skipped
    second = sync_service.sync_household(db, owner["household"]["id"])
    assert not second.runs and "try again" in second.skipped[0].reason


def test_scheduler_skips_recent_and_reauth(db, connection, monkeypatch):
    monkeypatch.setattr(sync_service, "get_provider", lambda name: FakeProvider())
    assert sync_service.sync_due(db) == 1
    assert sync_service.sync_due(db) == 0  # not due yet
    connection.status = ConnectionStatus.REAUTH_REQUIRED
    connection.last_attempt_at = utcnow() - timedelta(days=1)
    db.commit()
    assert sync_service.sync_due(db) == 0


def test_connection_api_and_delete_cascades(client, owner, db, monkeypatch):
    fake = FakeProvider()
    monkeypatch.setattr("app.services.connection_service.get_provider", lambda name: fake)
    monkeypatch.setattr(sync_service, "get_provider", lambda name: fake)

    resp = client.post("/api/v1/connections", json={"setup_token": "dGVzdA=="})
    assert resp.status_code == 201, resp.text
    conn_id = resp.json()["id"]

    # The initial sync runs as a background task after the response.
    connections = client.get("/api/v1/connections").json()
    assert connections[0]["account_count"] == 3
    assert db.query(SyncRun).filter_by(trigger="initial").count() == 1

    summary = client.get("/api/v1/summary", params={"scope": "household"}).json()
    assert summary["net_worth_cents"] == 253417 - 81240 + 1543210

    txns = client.get("/api/v1/transactions", params={"scope": "household"}).json()["items"]
    assert len(txns) == 4 and all(not t["editable"] for t in txns)

    assert client.delete(f"/api/v1/connections/{conn_id}").status_code == 204
    db.expire_all()
    assert db.query(Account).count() == 0
    assert db.query(Transaction).count() == 0
