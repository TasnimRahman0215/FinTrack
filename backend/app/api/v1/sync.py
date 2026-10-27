"""/api/v1/sync: "Sync now" and sync history. Called by frontend/src/api/sync.js."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_auth, get_db, require_role
from app.models.enums import Role
from app.repositories import sync_run_repo
from app.schemas.sync import SyncResultOut, SyncRunOut
from app.services import sync_service
from app.services.auth_service import AuthContext

router = APIRouter(prefix="/sync", tags=["sync"])


@router.post("", response_model=SyncResultOut)
def sync_now(
    ctx: AuthContext = Depends(require_role(Role.CONTRIBUTOR)), db: Session = Depends(get_db)
) -> SyncResultOut:
    """Sync every connection now, skipping ones synced within the cooldown."""
    return sync_service.sync_household(db, ctx.household_id)


@router.get("/runs", response_model=list[SyncRunOut])
def recent_runs(
    ctx: AuthContext = Depends(get_auth), db: Session = Depends(get_db)
) -> list[SyncRunOut]:
    """The most recent sync runs, newest first."""
    return [
        SyncRunOut.model_validate(r)
        for r in sync_run_repo.recent_for_household(db, ctx.household_id)
    ]
