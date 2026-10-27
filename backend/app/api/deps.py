"""FastAPI dependencies shared by every router: DB session, current user, role checks, scope.

Routers in app/api/v1/ declare what they need, e.g. `ctx = Depends(require_role(Role.CONTRIBUTOR))`
or `scope = Depends(get_scope)`, and FastAPI runs these before the endpoint.
"""

from collections.abc import Callable

from fastapi import Depends, Query, Request
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import Forbidden, Unauthorized
from app.core.scope import Scope, resolve_scope
from app.db.session import get_db
from app.models.enums import Role
from app.services import auth_service
from app.services.auth_service import AuthContext

__all__ = ["get_db", "get_auth", "require_role", "get_scope", "client_ip"]


def get_auth(request: Request, db: Session = Depends(get_db)) -> AuthContext:
    """The signed-in user and their household/role, from the session cookie. 401 if missing."""
    token = request.cookies.get(get_settings().cookie_name)
    if not token:
        raise Unauthorized("Please sign in.")
    ctx = auth_service.resolve_session(db, token)
    if ctx is None:
        raise Unauthorized("Your session has expired. Please sign in again.")
    return ctx


def require_role(minimum: Role) -> Callable[..., AuthContext]:
    """Usage: `ctx: AuthContext = Depends(require_role(Role.CONTRIBUTOR))`."""

    def _dependency(ctx: AuthContext = Depends(get_auth)) -> AuthContext:
        if not ctx.has_role(minimum):
            raise Forbidden(f"This action needs the {minimum.value} role or higher.")
        return ctx

    return _dependency


def get_scope(
    scope: str = Query("me", description="me | household | member:<user_id>"),
    ctx: AuthContext = Depends(get_auth),
    db: Session = Depends(get_db),
) -> Scope:
    """The accounts visible under `?scope=` (see app/core/scope.py)."""
    return resolve_scope(db, household_id=ctx.household_id, user_id=ctx.user.id, raw=scope)


def client_ip(request: Request) -> str:
    """Rate-limit key. Behind nginx this is the proxy's IP, so limits are effectively global."""
    return request.client.host if request.client else "unknown"
