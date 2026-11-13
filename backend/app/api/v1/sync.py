"""/api/v1/sync: "Sync now" and sync history. Called by frontend/src/api/sync.js."""

from fastapi import APIRouter, BackgroundTasks, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import get_auth, get_db, require_role
from app.db.session import SessionLocal
from app.models import Connection
from app.models.enums import Role
from app.repositories import sync_run_repo
from app.schemas.sync import SyncRunOut, SyncStartOut
from app.services import connection_service, sync_service
from app.services.auth_service import AuthContext

router = APIRouter(prefix="/sync", tags=["sync"])


def _run_claimed(connection_ids: list[int]) -> None:
    """Background task (after the response): sync the connections claimed by the request."""
    with SessionLocal() as db:
        for connection_id in connection_ids:
            connection = db.get(Connection, connection_id)
            if connection is not None:
                sync_service.run_claimed(db, connection, trigger="manual")


@router.post("", response_model=SyncStartOut, status_code=status.HTTP_202_ACCEPTED)
def sync_now(
    background: BackgroundTasks,
    ctx: AuthContext = Depends(require_role(Role.CONTRIBUTOR)),
    db: Session = Depends(get_db),
) -> SyncStartOut:
    """Start syncing every connection, skipping ones synced within the cooldown.

    Returns right away; the syncs run in the background (a household with several connections
    could otherwise outlast the proxy timeout). GET /connections shows `syncing` until they end.
    """
    result = sync_service.start_household_sync(db, ctx.household_id)
    if result.started:
        background.add_task(_run_claimed, result.started)
    return result


@router.get("/runs", response_model=list[SyncRunOut])
def recent_runs(
    ctx: AuthContext = Depends(get_auth), db: Session = Depends(get_db)
) -> list[SyncRunOut]:
    """The most recent sync runs of connections you manage, newest first.

    Other members' connections are left out: their counts and provider errors can reveal private
    accounts.
    """
    managed = connection_service.managed_connection_ids(db, ctx)
    return [
        SyncRunOut.model_validate(r)
        for r in sync_run_repo.recent_for_household(db, ctx.household_id, managed)
    ]
