"""Connection request/response bodies for api/v1/connections.py."""

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, StringConstraints

from app.schemas.common import ORMModel


class ConnectionCreate(BaseModel):
    """The SimpleFIN setup token (or an access URL) pasted in Settings."""

    setup_token: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4096)
    ]


class ConnectionOut(ORMModel):
    """A connection as shown in Settings. The encrypted credentials are never included."""

    id: int
    provider: str
    label: str
    status: str
    added_by_user_id: int | None
    last_synced_at: datetime | None
    last_error: str | None
    created_at: datetime
    account_count: int = 0
