"""/api/v1/summary: dashboard totals for a scope. Called by frontend/src/api/summary.js."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_auth, get_db, get_scope
from app.core.scope import Scope
from app.schemas.summary import SummaryOut
from app.services import summary_service
from app.services.auth_service import AuthContext

router = APIRouter(prefix="/summary", tags=["summary"])


@router.get("", response_model=SummaryOut)
def get_summary(
    scope: Scope = Depends(get_scope),
    ctx: AuthContext = Depends(get_auth),
    db: Session = Depends(get_db),
) -> SummaryOut:
    """Net worth, assets, liabilities and breakdowns for the accounts in the scope."""
    return summary_service.summary(db, scope, ctx.household_id)
