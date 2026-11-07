from parley.sql.builder import MetricRegistry

TAXI_METRICS = MetricRegistry(
    expressions={
        "count_trips": "COUNT(*)",
        "avg_fare": "AVG(fare_amount)",
        "avg_tip": "AVG(tip_amount)",
        "avg_trip_distance": "AVG(trip_distance)",
        "avg_total": "AVG(total_amount)",
        "sum_total": "SUM(total_amount)",
        "avg_tip_pct": "AVG(tip_amount / NULLIF(fare_amount, 0))",
    },
    descriptions={
        "count_trips": "number of trips",
        "avg_fare": "average fare_amount",
        "avg_tip": "average tip_amount",
        "avg_trip_distance": "average trip_distance",
        "avg_total": "average total_amount",
        "sum_total": "sum of total_amount",
        "avg_tip_pct": "average tip as a fraction of fare_amount",
    },
)
