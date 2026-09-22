"""Gold layer: analytics views answering "how much is each station used?".

Two complementary angles on "usage", combined into one overview:

1. Operational utilization (mart_station_utilization), from historized
   station_status snapshots:
   - avg_occupancy_rate: average bikes_available / capacity. High values
     mean bikes pile up (low outbound demand)
   - pct_time_stockout: share of snapshots where the station had 0 bikes
     (unmet rental demand -> a strong "this station is popular" signal).
   - pct_time_full: share of snapshots where the station had 0 free docks
     (unmet return demand).

2. Commercial demand (mart_station_demand), from pass_sales that carry a
   RelatedBikeStationId: count and
   revenue of sales for a station.

These are implmented as SQL views (not materialized tables) so they are
always in sync with the latest loaded data and are directly query-able by
analysts via any DuckDB client.
"""

from __future__ import annotations

import duckdb

VIEWS_SQL = """
CREATE OR REPLACE VIEW mart_station_utilization AS
SELECT
    s.station_id,
    d.name,
    d.capacity,
    count(*) AS snapshots_observed,
    round(avg(s.occupancy_rate), 3) AS avg_occupancy_rate,
    round(avg(CASE WHEN s.num_bikes_available = 0 THEN 1.0 ELSE 0.0 END), 3) AS pct_time_stockout,
    round(avg(CASE WHEN s.num_docks_available = 0 THEN 1.0 ELSE 0.0 END), 3) AS pct_time_full,
    max(s.ingested_at) AS last_observed_at
FROM fct_station_status s
JOIN dim_station d USING (station_id)
GROUP BY s.station_id, d.name, d.capacity;

CREATE OR REPLACE VIEW mart_station_demand AS
SELECT
    d.station_id,
    d.name,
    count(p.transaction_id) AS station_linked_sales,
    round(sum(p.price_nok), 2) AS station_linked_revenue_nok
FROM dim_station d
LEFT JOIN fct_pass_sales p ON p.related_station_id = d.station_id
GROUP BY d.station_id, d.name;

CREATE OR REPLACE VIEW mart_station_overview AS
SELECT
    u.station_id,
    u.name,
    u.capacity,
    u.snapshots_observed,
    u.avg_occupancy_rate,
    u.pct_time_stockout,
    u.pct_time_full,
    dm.station_linked_sales,
    dm.station_linked_revenue_nok
FROM mart_station_utilization u
LEFT JOIN mart_station_demand dm USING (station_id)
ORDER BY u.pct_time_stockout DESC;
"""


def create_marts(con: duckdb.DuckDBPyConnection) -> None:
    con.execute(VIEWS_SQL)
