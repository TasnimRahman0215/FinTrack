"""Sign up, log in, log out and session lookup.

Used by api/v1/auth.py, and by api/deps.py (`resolve_session`) on every authenticated request.
The browser holds a random session token in an HttpOnly cookie; the database stores only its hash.
"""

from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core import security
from app.core.clock import utcnow
from app.core.config import get_settings
from app.core.errors import Conflict, Forbidden, Unauthorized
from app.models import Household, User, UserSession
from app.models.enums import ROLE_RANK, Role
from app.repositories import household_repo, session_repo, user_repo
from app.schemas.auth import HouseholdBrief, LoginIn, MeOut, SignupIn, UserOut


@dataclass
class AuthContext:
    """Who is making the request, and in which household, with which role."""

    user: User
    session: UserSession
    household_id: int
    role: Role

    def has_role(self, minimum: Role) -> bool:
        return ROLE_RANK[self.role] >= ROLE_RANK[minimum]


def signup_enabled(db: Session) -> bool:
    """ALLOW_SIGNUP, except the very first account is always allowed (it becomes the owner)."""
    return get_settings().allow_signup or user_repo.count(db) == 0


def signup(db: Session, data: SignupIn, *, user_agent: str | None) -> tuple[str, AuthContext]:
    """Create user + their own household + owner membership + session, atomically."""
    if not signup_enabled(db):
        raise Forbidden("Sign-ups are disabled on this server.", code="signup_disabled")
    if user_repo.get_by_email(db, data.email):
        raise Conflict("An account with this email already exists.", code="email_taken")

    try:
        user = user_repo.create(
            db,
            email=data.email,
            display_name=data.display_name,
            password_hash=security.hash_password(data.password),
        )
        household = household_repo.create(
            db, name=f"{user.display_name}'s Household", created_by_user_id=user.id
        )
        household_repo.add_member(db, household_id=household.id, user_id=user.id, role=Role.OWNER)
        token, session = _create_session(db, user, household.id, user_agent)
        db.commit()
    except IntegrityError as exc:  # concurrent signup with the same email
        db.rollback()
        raise Conflict("An account with this email already exists.", code="email_taken") from exc

    return token, AuthContext(
        user=user, session=session, household_id=household.id, role=Role.OWNER
    )


def login(db: Session, data: LoginIn, *, user_agent: str | None) -> tuple[str, AuthContext]:
    """Returns the raw session token (for the cookie) and the auth context."""
    user = user_repo.get_by_email(db, data.email)
    if not security.verify_password(user.password_hash if user else None, data.password):
        raise Unauthorized("Invalid email or password.", code="invalid_credentials")
    assert user is not None

    # Transparently upgrade old hashes while we have the plain password.
    if security.password_needs_rehash(user.password_hash):
        user.password_hash = security.hash_password(data.password)

    membership = household_repo.first_membership(db, user.id)
    if membership is None:
        raise Forbidden("This account isn't part of any household.", code="no_household")
    token, session = _create_session(db, user, membership.household_id, user_agent)
    session_repo.delete_expired(db)
    db.commit()

    return token, AuthContext(
        user=user, session=session, household_id=membership.household_id, role=Role(membership.role)
    )


def logout(db: Session, token: str | None) -> None:
    if token:
        session_repo.delete_by_token_hash(db, security.hash_token(token))
        db.commit()


def resolve_session(db: Session, token: str) -> AuthContext | None:
    """Session cookie value -> AuthContext, or None if the session is unknown or expired."""
    session = session_repo.get_by_token_hash(db, security.hash_token(token))
    now = utcnow()
    if session is None or session.expires_at <= now:
        return None

    membership = None
    if session.active_household_id is not None:
        membership = household_repo.get_membership(
            db, household_id=session.active_household_id, user_id=session.user_id
        )
    if membership is None:  # removed from that household; fall back to another one
        membership = household_repo.first_membership(db, session.user_id)
        if membership is None:
            return None
        session.active_household_id = membership.household_id
        db.commit()

    # Sliding expiry: extend once less than half the lifetime remains.
    lifetime = timedelta(days=get_settings().session_days)
    if session.expires_at - now < lifetime / 2:
        session.expires_at = now + lifetime
        db.commit()

    return AuthContext(
        user=session.user,
        session=session,
        household_id=membership.household_id,
        role=Role(membership.role),
    )


def me(db: Session, ctx: AuthContext) -> MeOut:
    """The current user, household and role (GET /auth/me; the frontend's AuthContext)."""
    household = db.get(Household, ctx.household_id)
    return MeOut(
        user=UserOut.model_validate(ctx.user),
        household=HouseholdBrief.model_validate(household) if household else None,
        role=ctx.role,
    )


def _create_session(
    db: Session, user: User, household_id: int | None, user_agent: str | None
) -> tuple[str, UserSession]:
    token = security.new_token()
    session = session_repo.create(
        db,
        user_id=user.id,
        household_id=household_id,
        token_hash=security.hash_token(token),
        expires_at=utcnow() + timedelta(days=get_settings().session_days),
        user_agent=user_agent,
    )
    return token, session
