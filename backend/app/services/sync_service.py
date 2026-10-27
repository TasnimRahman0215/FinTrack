"""Sync orchestration: provider fetch -> upsert accounts/transactions -> balance snapshots ->
post-sync pipeline -> sync_runs record. Provider-agnostic: works with any `Provider`.

Called from three places: api/v1/connections.py (first sync after connecting), api/v1/sync.py
("Sync now") and jobs/sync_job.py (scheduled). See docs/architecture.md#sync for the overview.
"""

import logging
import threading
from collections import defaultdict
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.core import security
from app.core.clock import utcnow
from app.core.config import get_settings
from app.core.errors import AppError, ProviderAuthError
from app.models import Account, Connection, SyncRun, Transaction
from app.models.enums import ConnectionStatus, Source, SyncStatus, Visibility
from app.pipeline.registry import run_pipeline
from app.providers.base import FetchResult, Provider, ProviderAccount, ProviderTransaction
from app.providers.registry import get_provider
from app.repositories import account_repo, balance_repo, connection_repo, transaction_repo
from app.schemas.sync import SyncResultOut, SyncRunOut, SyncSkipped
from app.services.account_service import guess_kind

log = logging.getLogger(__name__)

# One sync per connection at a time (scheduler thread vs. "Sync now" button).
_locks: dict[int, threading.Lock] = defaultdict(threading.Lock)
_locks_guard = threading.Lock()

# Provider fields refreshed on every sync. User fields (notes, ...) are never touched.
_TXN_PROVIDER_FIELDS = (
    "date",
    "posted_at",
    "transacted_at",
    "amount_cents",
    "description",
    "payee",
    "memo",
    "pending",
)


def _lock_for(connection_id: int) -> threading.Lock:
    with _locks_guard:
        return _locks[connection_id]


def sync_connection(
    db: Session,
    connection: Connection,
    *,
    trigger: str = "manual",
    provider: Provider | None = None,
) -> SyncRun | None:
    """Sync one connection. Returns None if another sync of it is already running."""
    lock = _lock_for(connection.id)
    if not lock.acquire(blocking=False):
        return None
    try:
        return _sync_locked(db, connection, trigger, provider or get_provider(connection.provider))
    finally:
        lock.release()


def _sync_locked(db: Session, connection: Connection, trigger: str, provider: Provider) -> SyncRun:
    settings = get_settings()
    # Re-fetch a little before the last sync: pending items post later and can change amount/date.
    now = utcnow()
    earliest = now - timedelta(days=settings.initial_sync_days)
    start = (
        max(connection.last_synced_at - timedelta(days=settings.sync_overlap_days), earliest)
        if connection.last_synced_at
        else earliest
    )

    # Record the attempt up front so the run shows as "running" and the cooldown starts now.
    run = SyncRun(connection_id=connection.id, trigger=trigger, errors=[])
    db.add(run)
    connection.last_attempt_at = now
    db.commit()

    try:
        result = provider.fetch(security.decrypt(connection.credentials_enc), start, now)
    except ProviderAuthError as exc:
        return _fail(db, connection, run, exc.message, ConnectionStatus.REAUTH_REQUIRED)
    except AppError as exc:
        return _fail(db, connection, run, exc.message, ConnectionStatus.ERROR)
    # Raw exception text can include SQL parameters or provider data, and last_error is shown to
    # every household member, so the details only go to the server log.
    except Exception:  # noqa: BLE001
        log.exception("Sync of connection %s failed", connection.id)
        return _fail(
            db, connection, run, "Unexpected error; see the server log.", ConnectionStatus.ERROR
        )

    try:
        new_ids = _apply(db, connection, run, result, start)
    except Exception:  # noqa: BLE001
        log.exception("Saving sync results for connection %s failed", connection.id)
        return _fail(
            db,
            connection,
            run,
            "Couldn't save synced data; see the server log.",
            ConnectionStatus.ERROR,
        )

    connection.status = ConnectionStatus.ACTIVE
    connection.last_synced_at = now
    connection.last_error = "; ".join(result.errors) or None
    run.errors = list(result.errors)
    db.commit()  # persist synced data before processors run

    pipeline_errors = run_pipeline(db, connection.household_id, new_ids)
    run.errors = [*run.errors, *pipeline_errors]
    run.status = SyncStatus.PARTIAL if run.errors else SyncStatus.SUCCESS
    run.finished_at = utcnow()
    db.commit()
    log.info(
        "Synced connection %s: %s accounts, %s new, %s updated, %s removed",
        connection.id,
        run.accounts_seen,
        run.txns_new,
        run.txns_updated,
        run.txns_removed,
    )
    return run


def _apply(
    db: Session, connection: Connection, run: SyncRun, result: FetchResult, start: datetime
) -> list[int]:
    """Upsert accounts and transactions from `result`. Returns the IDs of new transactions."""
    existing = account_repo.by_provider_ids(db, connection.id)
    new_txns: list[Transaction] = []

    for p_account in result.accounts:
        account = existing.get(p_account.provider_account_id)
        if account is None:
            account = _create_account(db, connection, p_account)
        _update_account(account, p_account)
        balance_repo.upsert_snapshot(
            db,
            account_id=account.id,
            date=(account.balance_as_of or utcnow()).date(),
            balance_cents=account.balance_cents,
        )

        found = transaction_repo.existing_by_provider_ids(
            db, account.id, [t.provider_txn_id for t in p_account.transactions]
        )
        for p_txn in p_account.transactions:
            txn = found.get(p_txn.provider_txn_id)
            if txn is None:
                txn = _new_transaction(account.id, p_txn)
                db.add(txn)
                new_txns.append(txn)
                found[p_txn.provider_txn_id] = txn
            elif _update_transaction(txn, p_txn):
                run.txns_updated += 1

        run.txns_removed += transaction_repo.delete_stale_pending(
            db,
            account_id=account.id,
            since=start.date(),
            keep_provider_ids={t.provider_txn_id for t in p_account.transactions},
        )
        run.accounts_seen += 1

    db.flush()
    run.txns_new = len(new_txns)
    # Label the connection by its institutions, e.g. "Chase, Robinhood".
    if result.accounts:
        orgs = sorted({a.org_name for a in result.accounts if a.org_name})
        if orgs:
            connection.label = ", ".join(orgs)[:200]
    return [t.id for t in new_txns]


def _create_account(db: Session, connection: Connection, p: ProviderAccount) -> Account:
    """First time we see an account: guess its kind and give it to whoever connected it."""
    return account_repo.add(
        db,
        Account(
            household_id=connection.household_id,
            source=Source.SIMPLEFIN if connection.provider == "simplefin" else connection.provider,
            connection_id=connection.id,
            provider_account_id=p.provider_account_id,
            name=p.name,
            kind=guess_kind(p.name, p.org_name, p.balance_cents),
            owner_user_id=connection.added_by_user_id,  # whoever connected it; editable later
            visibility=Visibility.SHARED,
        ),
    )


def _update_account(account: Account, p: ProviderAccount) -> None:
    """Refresh provider fields only; user fields (display_name, owner, ...) are left alone."""
    account.name = p.name
    account.org_name = p.org_name
    account.currency = p.currency
    account.balance_cents = p.balance_cents
    account.available_cents = p.available_cents
    account.balance_as_of = p.balance_as_of or utcnow()


def _new_transaction(account_id: int, p: ProviderTransaction) -> Transaction:
    return Transaction(
        account_id=account_id,
        source=Source.SIMPLEFIN,
        provider_txn_id=p.provider_txn_id,
        date=p.date,
        posted_at=p.posted_at,
        transacted_at=p.transacted_at,
        amount_cents=p.amount_cents,
        description=p.description,
        payee=p.payee,
        memo=p.memo,
        pending=p.pending,
        raw_json=p.raw,
    )


def _update_transaction(txn: Transaction, p: ProviderTransaction) -> bool:
    """Refresh provider fields; returns True if anything changed."""
    changed = False
    for field in _TXN_PROVIDER_FIELDS:
        value = getattr(p, field)
        if getattr(txn, field) != value:
            setattr(txn, field, value)
            changed = True
    if changed:
        txn.raw_json = p.raw
    return changed


def _fail(
    db: Session, connection: Connection, run: SyncRun, message: str, status: ConnectionStatus
) -> SyncRun:
    """Discard partial changes and record the failure on the run and the connection."""
    db.rollback()
    connection.status = status
    connection.last_error = message
    run.status = SyncStatus.FAILED
    run.errors = [message]
    run.finished_at = utcnow()
    db.commit()
    return run


def sync_household(db: Session, household_id: int) -> SyncResultOut:
    """'Sync now' for every connection in a household, respecting a short cooldown so we stay
    under SimpleFIN's ~24 requests/day/connection limit."""
    cooldown = timedelta(minutes=get_settings().sync_cooldown_minutes)
    now = utcnow()
    runs: list[SyncRunOut] = []
    skipped: list[SyncSkipped] = []
    for connection, _ in connection_repo.list_for_household(db, household_id):
        if connection.last_attempt_at and now - connection.last_attempt_at < cooldown:
            wait = int((cooldown - (now - connection.last_attempt_at)).total_seconds() // 60) + 1
            skipped.append(
                SyncSkipped(
                    connection_id=connection.id, reason=f"Synced recently; try again in {wait} min."
                )
            )
            continue
        run = sync_connection(db, connection, trigger="manual")
        if run is None:
            skipped.append(SyncSkipped(connection_id=connection.id, reason="Already syncing."))
        else:
            runs.append(SyncRunOut.model_validate(run))
    return SyncResultOut(runs=runs, skipped=skipped)


def sync_due(db: Session) -> int:
    """Scheduler entry point: sync every connection whose last sync is older than the interval."""
    interval = timedelta(hours=get_settings().sync_interval_hours)
    now = utcnow()
    count = 0
    for connection in connection_repo.list_all(db):
        if connection.status == ConnectionStatus.REAUTH_REQUIRED:
            continue
        last = connection.last_attempt_at or connection.last_synced_at
        # 5-minute slack so a connection isn't skipped just because the check ran slightly early.
        if last and now - last < interval - timedelta(minutes=5):
            continue
        if sync_connection(db, connection, trigger="scheduled"):
            count += 1
    return count
