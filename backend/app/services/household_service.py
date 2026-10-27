"""The current household and its members (Settings page and the scope switcher).

Used by api/v1/household.py. Invites and member management will be added here.
"""

from sqlalchemy.orm import Session

from app.core.errors import NotFound
from app.models.enums import Role
from app.repositories import household_repo
from app.schemas.household import HouseholdOut, HouseholdUpdate, MemberOut
from app.services.auth_service import AuthContext


def get_household(db: Session, ctx: AuthContext) -> HouseholdOut:
    household = household_repo.get(db, ctx.household_id)
    if household is None:
        raise NotFound("Household not found.")
    members = [
        MemberOut(
            user_id=user.id,
            display_name=user.display_name,
            email=user.email,
            role=Role(membership.role),
            joined_at=membership.joined_at,
        )
        for membership, user in household_repo.list_members(db, household.id)
    ]
    return HouseholdOut(id=household.id, name=household.name, my_role=ctx.role, members=members)


def update_household(db: Session, ctx: AuthContext, data: HouseholdUpdate) -> HouseholdOut:
    household = household_repo.get(db, ctx.household_id)
    if household is None:
        raise NotFound("Household not found.")
    household.name = data.name
    db.commit()
    return get_household(db, ctx)
