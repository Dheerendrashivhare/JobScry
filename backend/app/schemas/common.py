"""Shared DTOs: pagination request params + paginated list envelope (CLAUDE.md §16)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


@dataclass(frozen=True)
class Pagination:
    """Resolved list-window params (kept here so services don't import the API layer)."""

    limit: int
    offset: int


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    limit: int
    offset: int
