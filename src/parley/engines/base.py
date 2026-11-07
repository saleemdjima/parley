from typing import Protocol, runtime_checkable


@runtime_checkable
class Engine(Protocol):
    name: str

    def source_expr(self) -> str:
        # The FROM target: read_parquet(...) for DuckDB, a table name for ClickHouse.
        ...

    def placeholder(self, index: int) -> str:
        # Parameter placeholder for the value at `index` (DuckDB '?', ClickHouse '%s').
        ...

    def catalog(self) -> dict[str, str]:
        # Column name -> type. The whitelist the builder validates against.
        ...

    def execute(self, sql: str, params: list) -> list[dict]: ...
