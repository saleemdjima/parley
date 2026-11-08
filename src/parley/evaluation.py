import argparse
import json
import logging
from dataclasses import dataclass
from pathlib import Path

from parley.domains.taxi import TAXI_METRICS
from parley.graph import metrics_dict
from parley.metrics import track
from parley.sql.builder import build_query
from parley.sql.intent import extract_intent
from parley.sql.router import Route, route

logger = logging.getLogger(__name__)

REFERENCE_PATH = (
    Path(__file__).resolve().parents[2] / "evals" / "reference_questions.jsonl"
)  # noqa: E501

# Fixed grounding so the golden SQL is deterministic regardless of PARQUET_PATH.
CANONICAL_COVERAGE = "2024"
CANONICAL_COLUMNS: dict[str, str] = {
    "VendorID": "BIGINT",
    "tpep_pickup_datetime": "TIMESTAMP",
    "tpep_dropoff_datetime": "TIMESTAMP",
    "passenger_count": "DOUBLE",
    "trip_distance": "DOUBLE",
    "RatecodeID": "DOUBLE",
    "PULocationID": "BIGINT",
    "DOLocationID": "BIGINT",
    "payment_type": "BIGINT",
    "fare_amount": "DOUBLE",
    "tip_amount": "DOUBLE",
    "tolls_amount": "DOUBLE",
    "total_amount": "DOUBLE",
}


class EvalEngine:
    # Fixed FROM target so expected SQL doesn't depend on the deployed PARQUET_PATH.
    name = "eval"

    def source_expr(self) -> str:
        return "read_parquet('nyc_yellow.parquet')"

    def placeholder(self, index: int) -> str:
        return "?"

    def catalog(self) -> dict[str, str]:
        return CANONICAL_COLUMNS

    def execute(self, sql: str, params: list) -> list[dict]:
        return []


def normalize(sql: str) -> str:
    return " ".join(sql.split())


@dataclass
class CaseResult:
    question: str
    expected_route: str
    actual_route: str
    expected_sql: str | None
    actual_sql: str | None
    expected_params: list | None
    actual_params: list | None
    metrics: dict
    passed: bool


def run_case(case: dict) -> CaseResult:
    question = case["question"]
    actual_sql: str | None = None
    actual_params: list | None = None
    with track() as metrics:
        decision = route(question)
        if decision == Route.sql:
            intent = extract_intent(
                question, list(CANONICAL_COLUMNS), CANONICAL_COVERAGE, TAXI_METRICS
            )
            sql, params = build_query(
                intent, CANONICAL_COLUMNS, EvalEngine(), TAXI_METRICS
            )
            actual_sql = normalize(sql)
            actual_params = params
    usage = metrics_dict(metrics)

    expected_route = case.get("route", "")
    expected_sql = normalize(case["sql"]) if case.get("sql") else None
    expected_params = case.get("params")

    passed = decision.value == expected_route
    if expected_sql is not None:
        passed = (
            passed and actual_sql == expected_sql and actual_params == expected_params
        )

    return CaseResult(
        question=question,
        expected_route=expected_route,
        actual_route=decision.value,
        expected_sql=expected_sql,
        actual_sql=actual_sql,
        expected_params=expected_params,
        actual_params=actual_params,
        metrics=usage,
        passed=passed,
    )


def load_reference() -> list[dict]:
    with REFERENCE_PATH.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def record() -> None:
    cases = load_reference()
    for case in cases:
        result = run_case(case)
        case["route"] = result.actual_route
        if result.actual_sql is not None:
            case["sql"] = result.actual_sql
            case["params"] = result.actual_params
        else:
            case.pop("sql", None)
            case.pop("params", None)
    with REFERENCE_PATH.open("w", encoding="utf-8") as handle:
        for case in cases:
            handle.write(json.dumps(case, ensure_ascii=False) + "\n")
    print(f"Recorded {len(cases)} golden cases -> {REFERENCE_PATH}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="parley reference-question regression harness"
    )
    parser.add_argument(
        "--record", action="store_true", help="overwrite goldens from current output"
    )
    args = parser.parse_args()

    if args.record:
        record()
        return 0

    results = [run_case(case) for case in load_reference()]
    passed = sum(1 for result in results if result.passed)
    total_cost = sum(result.metrics["cost_usd"] for result in results)
    total_latency = sum(result.metrics["latency_s"] for result in results)
    total_tokens = sum(
        result.metrics["input_tokens"] + result.metrics["output_tokens"]
        for result in results
    )

    for result in results:
        print(f"[{'PASS' if result.passed else 'FAIL'}] {result.question}")
        if not result.passed:
            print(f"route expected={result.expected_route} actual={result.actual_route}")
            if result.expected_sql != result.actual_sql:
                print(f"sql expected={result.expected_sql}")
                print(f"actual={result.actual_sql}")
            if result.expected_params != result.actual_params:
                print(
                    f"params expected={result.expected_params} "
                    f"actual={result.actual_params}"
                )

    print(
        f"\n{passed}/{len(results)} passed | latency {total_latency:.1f}s | "
        f"tokens {total_tokens} | cost ${total_cost:.4f}"
    )
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
