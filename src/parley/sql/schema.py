from enum import StrEnum

from pydantic import BaseModel, Field


class Comparator(StrEnum):
    eq = "="
    ne = "!="
    lt = "<"
    lte = "<="
    gt = ">"
    gte = ">="


class Filter(BaseModel):
    column: str
    op: Comparator
    value: float | int | str


class QueryIntent(BaseModel):
    metric: str
    group_by: str | None = None
    filters: list[Filter] = Field(default_factory=list)
    order_desc: bool = True
    limit: int = 20
