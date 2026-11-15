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
    # order_desc and top_n only shape a grouped ranking.
    order_desc: bool = True
    top_n: int | None = Field(
        default=None,
        description="Only set when the user explicitly asks for a fixed number of "
        "ranked results (e.g. 'top 5 payment types'). Leave null otherwise.",
    )
