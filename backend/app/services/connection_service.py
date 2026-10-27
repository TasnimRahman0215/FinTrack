"""Adding, listing and removing provider connections (e.g. a SimpleFIN access URL).

Used by api/v1/connections.py. Credentials are encrypted here before they reach the database.
"""

from sqlalchemy.orm import Session

from app.core import security
from app.core.errors import NotFound
from app.models import Connection
from app.providers.registry import get_provider
from app.repositories import connection_repo
from app.schemas.connection import ConnectionOut
from app.services.auth_service import AuthContext


def _to_out(connection: Connection, account_count: int) -> ConnectionOut:
    out = ConnectionOut.model_validate(connection)
    out.account_count = account_count
    return out


def list_connections(db: Session, ctx: AuthContext) -> list[ConnectionOut]:
    return [_to_out(c, n) for c, n in connection_repo.list_for_household(db, ctx.household_id)]


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


def to_out(connection: Connection) -> ConnectionOut:
    """Schema for one connection (used right after creating it)."""
    return _to_out(connection, len(connection.accounts))


def delete(db: Session, ctx: AuthContext, connection_id: int) -> None:
    """Removes the connection and every account and transaction it synced."""
    connection = connection_repo.get(db, household_id=ctx.household_id, connection_id=connection_id)
    if connection is None:
        raise NotFound("Connection not found.")
    db.delete(connection)
    db.commit()
