"""/api/v1/household: the active household and its members.

Called by frontend/src/api/household.js (scope switcher and Settings).
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_auth, get_db, require_role
from app.models.enums import Role
from app.schemas.household import HouseholdOut, HouseholdUpdate
from app.services import household_service
from app.services.auth_service import AuthContext

router = APIRouter(prefix="/household", tags=["household"])


@router.get("", response_model=HouseholdOut)
def get_household(
    ctx: AuthContext = Depends(get_auth), db: Session = Depends(get_db)
) -> HouseholdOut:
    """The household name, your role, and its members."""
    return household_service.get_household(db, ctx)


@router.patch("", response_model=HouseholdOut)
def update_household(
    data: HouseholdUpdate,
    ctx: AuthContext = Depends(require_role(Role.OWNER)),
    db: Session = Depends(get_db),
) -> HouseholdOut:
    """Rename the household (owner only)."""
    return household_service.update_household(db, ctx, data)
