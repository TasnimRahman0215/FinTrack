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
from app.core.errors import AppError, Conflict, Forbidden, NotFound, Unauthorized
from app.models import Household, User, UserSession
from app.models.enums import ROLE_RANK, Role
from app.repositories import household_repo, session_repo, user_repo
from app.schemas.auth import HouseholdBrief, LoginIn, MeOut, PasswordChangeIn, SignupIn, UserOut
from app.services import audit_service


@dataclass
class AuthContext:
    """Who is making the request, and in which household, with which role."""

    user: User
    session: UserSession
    household_id: int
    role: Role
    ip: str | None = None  # for the security event log (services/audit_service.py)
    user_agent: str | None = None

    def has_role(self, minimum: Role) -> bool:
        return ROLE_RANK[self.role] >= ROLE_RANK[minimum]


def signup_enabled(db: Session) -> bool:
    """ALLOW_SIGNUP, except the very first account is always allowed (it becomes the owner)."""
    return get_settings().allow_signup or user_repo.count(db) == 0


def signup(
    db: Session, data: SignupIn, *, user_agent: str | None, ip: str | None = None
) -> tuple[str, AuthContext]:
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
        audit_service.record(
            db, "signup", user_id=user.id, household_id=household.id, ip=ip, user_agent=user_agent
        )
        db.commit()
    except IntegrityError as exc:  # concurrent signup with the same email
        db.rollback()
        raise Conflict("An account with this email already exists.", code="email_taken") from exc

    return token, AuthContext(
        user=user,
        session=session,
        household_id=household.id,
        role=Role.OWNER,
        ip=ip,
        user_agent=user_agent,
    )


def login(
    db: Session, data: LoginIn, *, user_agent: str | None, ip: str | None = None
) -> tuple[str, AuthContext]:
    """Returns the raw session token (for the cookie) and the auth context."""
    user = user_repo.get_by_email(db, data.email)
    if not security.verify_password(user.password_hash if user else None, data.password):
        # Recorded for unknown emails too (without the email), so both cases do the same work
        # and timing doesn't reveal which emails have accounts. Owners see failures against
        # their own account in "Recent activity".
        audit_service.record(
            db, "login_failed", user_id=user.id if user else None, ip=ip, user_agent=user_agent
        )
        db.commit()
        raise Unauthorized("Invalid email or password.", code="invalid_credentials")
    assert user is not None

    # Transparently upgrade old hashes while we have the plain password.
    if security.password_needs_rehash(user.password_hash):
        user.password_hash = security.hash_password(data.password)

    membership = household_repo.first_membership(db, user.id)
    if membership is None:
        raise Forbidden("This account isn't part of any household.", code="no_household")
    token, session = _create_session(db, user, membership.household_id, user_agent)
    audit_service.record(
        db,
        "login",
        user_id=user.id,
        household_id=membership.household_id,
        ip=ip,
        user_agent=user_agent,
    )
    session_repo.delete_expired(db)
    audit_service.prune(db)
    db.commit()

    return token, AuthContext(
        user=user,
        session=session,
        household_id=membership.household_id,
        role=Role(membership.role),
        ip=ip,
        user_agent=user_agent,
    )


def logout(
    db: Session, token: str | None, *, ip: str | None = None, user_agent: str | None = None
) -> None:
    if not token:
        return
    session = session_repo.get_by_token_hash(db, security.hash_token(token))
    if session is None:
        return
    audit_service.record(
        db,
        "logout",
        user_id=session.user_id,
        household_id=session.active_household_id,
        ip=ip,
        user_agent=user_agent,
    )
    session_repo.delete_by_token_hash(db, session.token_hash)
    db.commit()


def resolve_session(db: Session, token: str) -> AuthContext | None:
    """Session cookie value -> AuthContext, or None if the session is unknown or expired."""
    session = session_repo.get_by_token_hash(db, security.hash_token(token))
    if session is None:
        return None
    now = utcnow()
    settings = get_settings()
    hard_limit = session.created_at + timedelta(days=settings.session_max_days)
    if session.expires_at <= now or hard_limit <= now:
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

    # Sliding expiry: extend once less than half the lifetime remains, but never past the hard
    # limit (SESSION_MAX_DAYS), so a stolen cookie can't be kept alive forever by using it.
    lifetime = timedelta(days=settings.session_days)
    if session.expires_at - now < lifetime / 2 and session.expires_at < hard_limit:
        session.expires_at = min(now + lifetime, hard_limit)
        db.commit()

    return AuthContext(
        user=session.user,
        session=session,
        household_id=membership.household_id,
        role=Role(membership.role),
    )


def change_password(db: Session, ctx: AuthContext, data: PasswordChangeIn) -> None:
    """Set a new password after checking the current one, and end every *other* session, so a
    leaked password or a stolen cookie stops working everywhere else."""
    if not security.verify_password(ctx.user.password_hash, data.current_password):
        audit_service.record_for(db, ctx, "password_change_failed")
        db.commit()
        raise AppError("Your current password is incorrect.", code="invalid_credentials")
    if data.new_password == data.current_password:
        raise AppError("Choose a password different from your current one.")
    ctx.user.password_hash = security.hash_password(data.new_password)
    session_repo.delete_for_user(db, ctx.user.id, keep_session_id=ctx.session.id)
    audit_service.record_for(db, ctx, "password_changed")
    db.commit()


def logout_everywhere(db: Session, ctx: AuthContext) -> None:
    """End every session of the signed-in user, this one included."""
    session_repo.delete_for_user(db, ctx.user.id)
    audit_service.record_for(db, ctx, "logout_all")
    db.commit()


def reset_password(db: Session, email: str, new_password: str) -> None:
    """Admin recovery (`fintrack reset-password`): set a password and end all its sessions."""
    user = user_repo.get_by_email(db, email)
    if user is None:
        raise NotFound(f"No account with the email {email}.")
    user.password_hash = security.hash_password(new_password)
    session_repo.delete_for_user(db, user.id)
    audit_service.record(db, "password_reset", user_id=user.id, ip="command line")
    db.commit()


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
