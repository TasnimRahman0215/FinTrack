"""Auth request/response bodies for api/v1/auth.py."""

from typing import Annotated

from pydantic import BaseModel, EmailStr, Field, StringConstraints

from app.models.enums import Role
from app.schemas.common import ORMModel

DisplayName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]
Password = Annotated[str, Field(min_length=8, max_length=128)]


class SignupIn(BaseModel):
    email: EmailStr
    display_name: DisplayName
    password: Password


class LoginIn(BaseModel):
    email: EmailStr
    password: Annotated[str, Field(min_length=1, max_length=128)]


class UserOut(ORMModel):
    id: int
    email: str
    display_name: str


class HouseholdBrief(ORMModel):
    id: int
    name: str


class MeOut(BaseModel):
    """Everything the frontend needs about the signed-in user (stored in AuthContext)."""

    user: UserOut
    household: HouseholdBrief | None
    role: Role | None


class AuthConfigOut(BaseModel):
    signup_enabled: bool
