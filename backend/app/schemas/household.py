"""Household response/update bodies for api/v1/household.py."""

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, StringConstraints

from app.models.enums import Role


class MemberOut(BaseModel):
    user_id: int
    display_name: str
    email: str
    role: Role
    joined_at: datetime


class HouseholdOut(BaseModel):
    id: int
    name: str
    my_role: Role
    members: list[MemberOut]


class HouseholdUpdate(BaseModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
