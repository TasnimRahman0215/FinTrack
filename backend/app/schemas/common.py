"""Shared schema building blocks."""

from pydantic import BaseModel, ConfigDict


class ORMModel(BaseModel):
    """Base for responses built straight from SQLAlchemy objects (`Model.model_validate(row)`)."""

    model_config = ConfigDict(from_attributes=True)


class Page[T](BaseModel):
    """Cursor-paginated list. Pass `next_cursor` back as `cursor` to get the next page."""

    items: list[T]
    next_cursor: str | None = None
