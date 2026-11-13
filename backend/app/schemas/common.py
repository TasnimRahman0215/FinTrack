"""Shared schema building blocks."""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

# Largest amount accepted from clients: $100 billion. Keeps sums far from 64-bit overflow
# and well inside the range JavaScript numbers represent exactly.
MAX_CENTS = 10**13
Cents = Annotated[int, Field(ge=-MAX_CENTS, le=MAX_CENTS)]


class ORMModel(BaseModel):
    """Base for responses built straight from SQLAlchemy objects (`Model.model_validate(row)`)."""

    model_config = ConfigDict(from_attributes=True)


class Page[T](BaseModel):
    """Cursor-paginated list. Pass `next_cursor` back as `cursor` to get the next page."""

    items: list[T]
    next_cursor: str | None = None
