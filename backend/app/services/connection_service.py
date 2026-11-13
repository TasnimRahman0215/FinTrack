"""Adding, listing and removing provider connections (e.g. a SimpleFIN access URL).

Used by api/v1/connections.py and api/v1/sync.py. Credentials are encrypted here before they reach
the database.

Privacy: one connection can hold several members' accounts, some of them private. So what a
viewer sees about a connection (its label, account count, last error, sync history) only covers
accounts that viewer may see, and only the person who added a connection can remove it (see
`can_manage`).
"""

from sqlalchemy.orm import Session

from app.core import security
from app.core.errors import Forbidden, NotFound
from app.models import Account, Connection
from app.models.enums import Role
from app.providers.registry import get_provider
from app.repositories import connection_repo, household_repo
from app.schemas.connection import ConnectionOut
from app.services import sync_service
from app.services.auth_service import AuthContext

# Shown instead of the real error to members who didn't add the connection: provider messages
# often name an institution ("Robinhood needs attention"), which may be someone's private account.
OTHERS_ERROR = "This connection reported a problem. The person who added it can see the details."


def can_manage(db: Session, ctx: AuthContext, connection: Connection) -> bool:
    """The member who added a connection manages it: sees its full details and can remove it.

    If that person has left the household (or their account was deleted), the household owner
    takes over, so a connection can never become impossible to remove.
    """
    if not ctx.has_role(Role.CONTRIBUTOR):
        return False
    if connection.added_by_user_id == ctx.user.id:
        return True
    return ctx.role == Role.OWNER and (
        connection.added_by_user_id is None
        or not household_repo.is_member(
            db, household_id=ctx.household_id, user_id=connection.added_by_user_id
        )
    )


def managed_connection_ids(db: Session, ctx: AuthContext) -> set[int]:
    return {
        c.id
        for c, _ in connection_repo.list_for_household(db, ctx.household_id)
        if can_manage(db, ctx, c)
    }


def to_out(
    db: Session,
    ctx: AuthContext,
    connection: Connection,
    *,
    total_accounts: int,
    visible: list[Account],
) -> ConnectionOut:
    """Settings view of a connection, limited to what this viewer may see."""
    manage = can_manage(db, ctx, connection)
    orgs = sorted({a.org_name for a in visible if a.org_name})
    if orgs:
        label = ", ".join(orgs)[:200]  # e.g. "Chase, Robinhood"
    elif total_accounts == 0:
        label = connection.label  # not synced yet: the label from connect time, e.g. the host
    else:
        label = "SimpleFIN"  # every account in it is someone else's private account

    last_error = connection.last_error
    if last_error and not manage:
        last_error = OTHERS_ERROR
    return ConnectionOut(
        id=connection.id,
        provider=connection.provider,
        label=label,
        status=connection.status,
        added_by_user_id=connection.added_by_user_id,
        last_synced_at=connection.last_synced_at,
        last_error=last_error,
        created_at=connection.created_at,
        account_count=len(visible),
        syncing=sync_service.is_syncing(connection),
        can_manage=manage,
    )


def list_connections(db: Session, ctx: AuthContext) -> list[ConnectionOut]:
    visible = connection_repo.visible_accounts_by_connection(
        db, household_id=ctx.household_id, user_id=ctx.user.id
    )
    return [
        to_out(db, ctx, c, total_accounts=n, visible=visible.get(c.id, []))
        for c, n in connection_repo.list_for_household(db, ctx.household_id)
    ]


def create(
    db: Session, ctx: AuthContext, setup_token: str, *, provider_name: str = "simplefin"
) -> Connection:
    """Claim the setup token with the provider and store the resulting credentials encrypted."""
    provider = get_provider(provider_name)
    # Setup tokens are single-use, so make sure the credentials can be stored before claiming one.
    security.check_encryption_key()
    credentials, label = provider.connect(setup_token)
    connection = Connection(
        household_id=ctx.household_id,
        added_by_user_id=ctx.user.id,
        provider=provider.name,
        label=label,
        credentials_enc=security.encrypt(credentials),
    )
    db.add(connection)
    db.commit()
    return connection


def delete(db: Session, ctx: AuthContext, connection_id: int) -> None:
    """Removes the connection and every account and transaction it synced."""
    connection = connection_repo.get(db, household_id=ctx.household_id, connection_id=connection_id)
    if connection is None:
        raise NotFound("Connection not found.")
    if not can_manage(db, ctx, connection):
        # Deleting cascades to every account it synced, including members' private ones.
        raise Forbidden("Only the person who added this connection can remove it.")
    db.delete(connection)
    db.commit()
