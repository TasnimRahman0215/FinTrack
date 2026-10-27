"""/api/v1/health: liveness check used by the Docker healthcheck (backend/Dockerfile)."""

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app import __version__
from app.api.deps import get_db

router = APIRouter(tags=["health"])


@router.get("/health")
def health(db: Session = Depends(get_db)) -> dict[str, str]:
    """OK when the API is up and the database answers."""
    db.execute(text("SELECT 1"))
    return {"status": "ok", "version": __version__}
