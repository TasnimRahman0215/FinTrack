"""/api/v1/connections: link a data source (SimpleFIN setup token), list and remove them.

Called by frontend/src/api/connections.js (Settings page).
"""

from fastapi import APIRouter, BackgroundTasks, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import get_auth, get_db, require_role
from app.db.session import SessionLocal
from app.models import Connection
from app.models.enums import Role
from app.schemas.connection import ConnectionCreate, ConnectionOut
from app.services import connection_service, sync_service
from app.services.auth_service import AuthContext

router = APIRouter(prefix="/connections", tags=["connections"])


def _initial_sync(connection_id: int) -> None:
    """Background task, so it opens its own session (the request's is closed by then)."""
    with SessionLocal() as db:
        connection = db.get(Connection, connection_id)
        if connection is not None:
            sync_service.sync_connection(db, connection, trigger="initial")


@router.get("", response_model=list[ConnectionOut])
def list_connections(
    ctx: AuthContext = Depends(get_auth), db: Session = Depends(get_db)
) -> list[ConnectionOut]:
    """The household's connections with status, last sync and last error."""
    return connection_service.list_connections(db, ctx)


@router.post("", response_model=ConnectionOut, status_code=status.HTTP_201_CREATED)
def create_connection(
    data: ConnectionCreate,
    background: BackgroundTasks,
    ctx: AuthContext = Depends(require_role(Role.CONTRIBUTOR)),
    db: Session = Depends(get_db),
) -> ConnectionOut:
    """Claim a SimpleFIN setup token, save the connection, and start the first sync."""
    connection = connection_service.create(db, ctx, data.setup_token)
    background.add_task(_initial_sync, connection.id)  # runs after the response is sent
    return connection_service.to_out(db, ctx, connection, total_accounts=0, visible=[])


@router.delete("/{connection_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_connection(
    connection_id: int,
    ctx: AuthContext = Depends(require_role(Role.CONTRIBUTOR)),
    db: Session = Depends(get_db),
) -> None:
    """Remove a connection with all accounts and transactions it synced."""
    connection_service.delete(db, ctx, connection_id)
