from datetime import datetime, timezone

import duckdb

from pipeline import load, metrics


def test_mart_station_overview_computes_utilization_and_demand():
    con = duckdb.connect(":memory:")
    con.execute(load.SCHEMA_SQL)
    now = datetime.now(timezone.utc)

    con.execute(
        "INSERT INTO dim_station VALUES ('1', 'Test Station', 'Addr 1', 59.9, 10.7, 10, ?, ?)",
        [now, now],
    )
    con.executemany(
        """
        INSERT INTO fct_station_status
        (run_id, station_id, ingested_at, is_installed, can_rent, can_return,
         num_bikes_available, num_docks_available, occupancy_rate)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            ("run1", "1", now, True, True, True, 0, 10, 0.0),
            ("run2", "1", now, True, True, True, 5, 5, 0.5),
        ],
    )
    con.execute(
        """
        INSERT INTO fct_pass_sales
        (transaction_id, user_id, pass_type, source, related_station_id,
         price_nok, purchase_timestamp, ingested_at, run_id)
        VALUES ('t1', 'u1', 'day_pass', 'station_qr', '1', 49, ?, ?, 'run1')
        """,
        [now, now],
    )

    metrics.create_marts(con)
    row = con.execute(
        """
        SELECT snapshots_observed, avg_occupancy_rate, pct_time_stockout,
               station_linked_sales, station_linked_revenue_nok
        FROM mart_station_overview WHERE station_id = '1'
        """
    ).fetchone()

    snapshots_observed, avg_occupancy_rate, pct_time_stockout, sales, revenue = row
    assert snapshots_observed == 2
    assert avg_occupancy_rate == 0.25
    assert pct_time_stockout == 0.5
    assert sales == 1
    assert revenue == 49
