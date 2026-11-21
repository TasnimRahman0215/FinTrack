"""Regression tests for the third security review: data at rest, logs, error responses, input
ranges, the security event log, encrypted backups and the deployment configuration."""

import base64
import datetime as dt
import logging
import os
import sqlite3
import stat
from pathlib import Path

import pytest
from cryptography.fernet import Fernet
from sqlalchemy.exc import IntegrityError
from typer.testing import CliRunner

from app.cli import app as cli_app
from app.core.config import get_settings
from app.core.files import private_dir
from app.db.session import SessionLocal, init_engine
from app.models import Account, SecurityEvent, Transaction
from app.models.enums import Source
from app.services import sync_service
from tests.conftest import PASSWORD, fake_password, make_client
from tests.test_sync import FakeProvider

REPO = Path(__file__).resolve().parents[2]


def mode(path: Path) -> int:
    return stat.S_IMODE(os.stat(path).st_mode)


# --- Data at rest: owner-only files --------------------------------------------------------------


def test_database_files_are_owner_only(tmp_path):
    db_file = tmp_path / "fresh" / "fintrack.db"
    engine = init_engine(f"sqlite:///{db_file}")
    with engine.begin() as conn:
        conn.exec_driver_sql("CREATE TABLE t (x)")  # creates the -wal/-shm files too
        conn.exec_driver_sql("INSERT INTO t VALUES (1)")
    assert mode(db_file) == 0o600
    assert mode(db_file.parent) == 0o700  # the folder FinTrack created
    for side in ("-wal", "-shm"):
        path = db_file.with_name(db_file.name + side)
        if path.exists():
            assert mode(path) == 0o600
    engine.dispose()


def test_existing_world_readable_database_is_tightened(tmp_path):
    db_file = tmp_path / "old.db"
    sqlite3.connect(db_file).close()
    os.chmod(db_file, 0o644)  # as created by earlier versions
    init_engine(f"sqlite:///{db_file}").dispose()
    assert mode(db_file) == 0o600


def test_existing_folders_are_left_alone(tmp_path):
    shared = tmp_path / "home"
    shared.mkdir(mode=0o755)
    os.chmod(shared, 0o755)
    private_dir(shared)
    assert mode(shared) == 0o755  # never chmod a folder FinTrack didn't create


# --- Logs: database errors never include the values ----------------------------------------------


def test_database_errors_hide_transaction_values(db, owner, caplog):
    db.add(
        Transaction(
            account_id=999_999,  # no such account: the insert fails
            source=Source.SIMPLEFIN,
            provider_txn_id="T1",
            date=dt.date(2026, 11, 1),
            amount_cents=-123456,
            description="RENT TO LANDLORD",
            payee="Dr. Smith Psychiatry",
        )
    )
    with pytest.raises(IntegrityError) as exc:
        db.commit()
    message = str(exc.value)
    assert "Psychiatry" not in message and "123456" not in message
    assert "hidden due to hide_parameters" in message


# --- Error responses never echo what was sent ---------------------------------------------------


def test_validation_errors_dont_echo_passwords(client, owner):
    too_short = fake_password()[:7]  # random, so finding it in the response means it was echoed
    resp = client.post(
        "/api/v1/auth/password",
        json={"current_password": PASSWORD, "new_password": too_short},
    )
    assert resp.status_code == 422
    assert too_short not in resp.text and '"input"' not in resp.text
    assert resp.json()["detail"][0]["loc"] == ["body", "new_password"]  # still says what failed

    with make_client() as c:
        resp = c.post("/api/v1/auth/login", json={"email": "a@example.com", "password": "Q" * 129})
        assert resp.status_code == 422 and "QQQQ" not in resp.text


# --- IDs outside the database's range are rejected, not crashed on -----------------------------

BIG = "99999999999999999999"


def test_oversized_ids_are_rejected_cleanly(client, owner):
    acct = client.post("/api/v1/accounts", json={"name": "Cash"}).json()
    client.post(
        "/api/v1/transactions",
        json={
            "account_id": acct["id"],
            "date": "2026-10-01",
            "amount_cents": -1,
            "description": "x",
        },
    )
    cursor = base64.urlsafe_b64encode(f"2026-01-01|{BIG}".encode()).decode()
    requests = [
        ("patch", f"/api/v1/accounts/{BIG}", {}),
        ("delete", f"/api/v1/accounts/{BIG}", None),
        ("patch", f"/api/v1/transactions/{BIG}", {}),
        ("delete", f"/api/v1/transactions/{BIG}", None),
        ("delete", f"/api/v1/connections/{BIG}", None),
        ("get", f"/api/v1/transactions?account_id={BIG}", None),
        ("get", f"/api/v1/transactions?cursor={cursor}", None),
        ("get", f"/api/v1/summary?scope=member:{BIG}", None),
        (
            "post",
            "/api/v1/transactions",
            {"account_id": int(BIG), "date": "2026-01-01", "amount_cents": -1, "description": "x"},
        ),
        ("post", "/api/v1/accounts", {"name": "x", "owner_user_id": int(BIG)}),
        ("patch", f"/api/v1/accounts/{acct['id']}", {"owner_user_id": int(BIG)}),
    ]
    for method, url, body in requests:
        kwargs = {"json": body} if body is not None else {}
        resp = getattr(client, method)(url, **kwargs)
        assert 400 <= resp.status_code < 500, (method, url, resp.status_code)


# --- Security event log ------------------------------------------------------------------------


def events(client):
    return [e["event"] for e in client.get("/api/v1/auth/activity").json()]


def test_sign_ins_and_failures_are_recorded_for_the_account_owner(engine, client, owner):
    email = owner["user"]["email"]
    with make_client() as attacker:
        attacker.post("/api/v1/auth/login", json={"email": email, "password": fake_password()})
        attacker.post("/api/v1/auth/login", json={"email": "nobody@example.com", "password": "x"})
    with make_client() as phone:
        phone.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
        phone.post("/api/v1/auth/logout")

    assert events(client)[:3] == ["logout", "login", "login_failed"]
    assert events(client)[-1] == "signup"
    entry = client.get("/api/v1/auth/activity").json()[0]
    assert set(entry) == {"event", "created_at", "ip", "user_agent"}  # no details exposed


def test_failed_logins_for_unknown_emails_are_recorded_without_the_email(engine, db):
    with make_client() as c:
        c.post("/api/v1/auth/login", json={"email": "probe@example.com", "password": "x"})
    row = db.query(SecurityEvent).filter_by(event="login_failed").one()
    assert row.user_id is None
    assert "probe@example.com" not in str(row.details)


def test_activity_only_shows_your_own_events(client, owner, partner):
    partner_client, _ = partner
    partner_client.post(
        "/api/v1/auth/password",
        json={"current_password": PASSWORD, "new_password": fake_password()},
    )
    assert "password_changed" in events(partner_client)
    assert "password_changed" not in events(client)


def test_access_changes_and_connections_are_recorded_without_financial_data(
    client, owner, db, monkeypatch, caplog
):
    fake = FakeProvider()
    monkeypatch.setattr("app.services.connection_service.get_provider", lambda name: fake)
    monkeypatch.setattr(sync_service, "get_provider", lambda name: fake)
    caplog.set_level(logging.INFO, logger="fintrack.audit")

    conn_id = client.post("/api/v1/connections", json={"setup_token": "dGVzdA=="}).json()["id"]
    card = db.query(Account).filter_by(name="Gold Card").one()
    client.patch(f"/api/v1/accounts/{card.id}", json={"visibility": "shared"})
    client.patch(f"/api/v1/accounts/{card.id}", json={"display_name": "Amex"})  # not access
    client.delete(f"/api/v1/connections/{conn_id}")

    recorded = events(client)
    assert recorded[:3] == ["connection_removed", "account_access_changed", "connection_added"]
    change = db.query(SecurityEvent).filter_by(event="account_access_changed").one()
    assert change.details["visibility_to"] == "shared" and change.details["account_id"] == card.id

    audit_lines = " ".join(r.getMessage() for r in caplog.records if r.name == "fintrack.audit")
    assert "connection_added" in audit_lines  # the log really was written
    for secret in ("Gold Card", "Amex", "American Express", "Whole Foods", "2534"):
        assert secret not in audit_lines


def test_rate_limited_logins_are_logged_but_not_stored(engine, client, owner, db, caplog):
    caplog.set_level(logging.WARNING, logger="fintrack.audit")
    for _ in range(11):
        client.post(
            "/api/v1/auth/login",
            json={"email": owner["user"]["email"], "password": fake_password()},
        )
    assert any("login_rate_limited" in r.getMessage() for r in caplog.records)
    assert db.query(SecurityEvent).filter(SecurityEvent.event.like("%rate%")).count() == 0


# --- Encrypted backups -------------------------------------------------------------------------


@pytest.fixture
def db_file(tmp_path, monkeypatch, client, owner):
    """Point the CLI at the test database (which already holds a signed-up owner)."""
    url = str(SessionLocal.kw["bind"].url)
    monkeypatch.setenv("DATABASE_URL", url)
    get_settings.cache_clear()
    return Path(url.removeprefix("sqlite:///"))


def test_backups_are_encrypted_private_and_restorable(tmp_path, db_file):
    runner = CliRunner()
    out = tmp_path / "backups"
    result = runner.invoke(cli_app, ["backup", "--dest", str(out)])
    assert result.exit_code == 0, result.output
    [backup] = out.glob("*.db.enc")
    assert mode(backup) == 0o600 and mode(out) == 0o700
    assert not backup.read_bytes().startswith(b"SQLite format 3")
    assert list(out.glob("*.tmp")) == [] and list(out.glob("*.db")) == []  # no plaintext left

    restored = tmp_path / "restored.db"
    result = runner.invoke(cli_app, ["restore-backup", str(backup), "--to", str(restored)])
    assert result.exit_code == 0, result.output
    assert mode(restored) == 0o600
    with sqlite3.connect(restored) as conn:
        assert conn.execute("SELECT email FROM users").fetchall() == [("alex@example.com",)]
    # The restored file opens normally through the app (which switches it back to WAL).
    engine = init_engine(f"sqlite:///{restored}")
    with engine.connect() as conn:
        assert conn.exec_driver_sql("PRAGMA journal_mode").scalar() == "wal"
        assert conn.exec_driver_sql("SELECT count(*) FROM users").scalar() == 1
    engine.dispose()


def test_tampered_or_wrong_key_backups_are_refused(tmp_path, db_file, monkeypatch):
    runner = CliRunner()
    out = tmp_path / "backups"
    runner.invoke(cli_app, ["backup", "--dest", str(out)])
    [backup] = out.glob("*.db.enc")

    tampered = tmp_path / "tampered.db.enc"
    data = bytearray(backup.read_bytes())
    data[60] ^= 0x01
    tampered.write_bytes(bytes(data))
    result = runner.invoke(cli_app, ["restore-backup", str(tampered), "--to", str(tmp_path / "a")])
    assert result.exit_code == 1 and "Can't decrypt" in result.output

    monkeypatch.setenv("ENCRYPTION_KEY", Fernet.generate_key().decode())
    get_settings.cache_clear()
    result = runner.invoke(cli_app, ["restore-backup", str(backup), "--to", str(tmp_path / "b")])
    assert result.exit_code == 1 and "different ENCRYPTION_KEY" in result.output


def test_backup_needs_a_key_unless_plaintext_is_requested(tmp_path, db_file, monkeypatch):
    monkeypatch.setenv("ENCRYPTION_KEY", "")
    get_settings.cache_clear()
    runner = CliRunner()
    out = tmp_path / "backups"
    result = runner.invoke(cli_app, ["backup", "--dest", str(out)])
    assert result.exit_code == 1 and "ENCRYPTION_KEY" in result.output
    assert not out.exists() or list(out.iterdir()) == []

    for _ in range(3):
        assert (
            runner.invoke(
                cli_app, ["backup", "--dest", str(out), "--plaintext", "--keep", "2"]
            ).exit_code
            == 0
        )
    plain = list(out.glob("*.db"))
    assert plain and all(mode(p) == 0o600 for p in plain)
    assert len(plain) <= 2  # pruned


# --- Deployment configuration ------------------------------------------------------------------


def test_compose_is_hardened_and_local_only_by_default():
    compose = (REPO / "docker-compose.yml").read_text()
    for setting in ("read_only: true", "cap_drop: [ALL]", '"no-new-privileges:true"'):
        assert setting in compose
    assert compose.count("<<: *hardened") == 3  # backend, frontend, worker
    assert '"${FRONTEND_BIND:-127.0.0.1}:${FRONTEND_PORT:-3000}:8080"' in compose
    assert '"127.0.0.1:${BACKEND_PORT:-8000}:8000"' in compose


def test_base_images_are_pinned_by_digest():
    for dockerfile in (REPO / "backend" / "Dockerfile", REPO / "frontend" / "Dockerfile"):
        refs = [
            line.split()[1] if line.startswith("FROM") else line.split("--from=")[1].split()[0]
            for line in dockerfile.read_text().splitlines()
            if line.startswith("FROM") or line.startswith("COPY --from=")
        ]
        refs = [r for r in refs if ":" in r or "/" in r]  # images, not build-stage names
        assert refs, dockerfile
        for ref in refs:
            assert "@sha256:" in ref, f"{dockerfile.name}: {ref} isn't pinned by digest"
