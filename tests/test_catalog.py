import duckdb

from parley.config import settings
from parley.sql import catalog as catalog_mod
from parley.sql.catalog import Catalog, SourceInfo, parse_period


def test_parse_period_year_month() -> None:
    label, year = parse_period("https://x/yellow_tripdata_2024-03.parquet")
    assert label == "2024-03"
    assert year == 2024


def test_parse_period_year_only() -> None:
    assert parse_period("gs://bucket/dvf_2019.parquet") == ("2019", 2019)


def test_parse_period_no_period() -> None:
    label, year = parse_period("data/trips.parquet")
    assert label == "trips.parquet"
    assert year is None


def test_coverage_single_year() -> None:
    cat = Catalog([], {}, {}, 0, 2024, 2024)
    assert cat.coverage() == "2024"


def test_coverage_range() -> None:
    cat = Catalog([], {}, {}, 0, 2017, 2024)
    assert cat.coverage() == "2017-2024"


def test_coverage_unknown() -> None:
    cat = Catalog([], {}, {}, 0, None, None)
    assert cat.coverage() == "unknown"


def test_build_catalog_layer_reconciles_schema(tmp_path, monkeypatch) -> None:
    # Two files with drifting schemas: common column is {a}, union is {a,b,c}.
    first = tmp_path / "trips_2023.parquet"
    second = tmp_path / "trips_2024.parquet"
    con = duckdb.connect()
    con.execute(f"COPY (SELECT 1 AS a, 2 AS b) TO '{first.as_posix()}' (FORMAT PARQUET)")
    con.execute(f"COPY (SELECT 1 AS a, 3 AS c) TO '{second.as_posix()}' (FORMAT PARQUET)")

    monkeypatch.setattr(catalog_mod, "get_connection", lambda: con)
    monkeypatch.setattr(
        settings, "parquet_path", f"{first.as_posix()},{second.as_posix()}"
    )
    monkeypatch.setattr(catalog_mod, "cached_catalog", None)

    cat = catalog_mod.build_catalog_layer()

    assert cat.total_rows == 2
    assert cat.coverage() == "2023-2024"
    assert set(cat.all_columns) == {"a", "b", "c"}
    assert set(cat.columns) == {"a"}
    assert isinstance(cat.sources[0], SourceInfo)
