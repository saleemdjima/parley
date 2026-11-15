from parley.sql.builder import MetricRegistry

TAXI_METRICS = MetricRegistry(
    expressions={
        "avg_tip_pct": "AVG(tip_amount / NULLIF(fare_amount, 0))",
    },
    descriptions={
        "avg_tip_pct": "average tip as a fraction of fare_amount",
    },
)
