"""Load step: idempotent writes into typed DuckDB tables (silver layer).

- dim_station is upserted (station metadata can change over time).
- fct_station_status is append-only: every pipeline run adds one snapshot
  row per station, which is what lets us build a time series out of an
  API that only returns "right now".
- fct_pass_sales is append-only with a deduplication guard on transaction_id,
  since a re-run should never double count a sale.
"""

from __future__ import annotations

import logging
from datetime import datetime

import duckdb

from .config import DB_PATH
from .models import PassSale, StationInformation, StationStatus

logger = logging.getLogger(__name__)

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS dim_station (
    station_id VARCHAR PRIMARY KEY,
    name VARCHAR,
    address VARCHAR,
    lat DOUBLE,
    lon DOUBLE,
    capacity INTEGER,
    first_seen_at TIMESTAMP,
    last_seen_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS fct_station_status (
    run_id VARCHAR,
    station_id VARCHAR,
    ingested_at TIMESTAMP,
    is_installed BOOLEAN,
    can_rent BOOLEAN,
    can_return BOOLEAN,
    num_bikes_available INTEGER,
    num_docks_available INTEGER,
    occupancy_rate DOUBLE
);

CREATE TABLE IF NOT EXISTS fct_pass_sales (
    transaction_id VARCHAR PRIMARY KEY,
    user_id VARCHAR,
    pass_type VARCHAR,
    source VARCHAR,
    related_station_id VARCHAR,
    price_nok DOUBLE,
    purchase_timestamp TIMESTAMP,
    ingested_at TIMESTAMP,
    run_id VARCHAR
);
"""


def get_connection() -> duckdb.DuckDBPyConnection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(DB_PATH))
    con.execute(SCHEMA_SQL)
    return con


def load_dim_station(
    con: duckdb.DuckDBPyConnection, records: list[StationInformation], now: datetime
) -> None:
    for r in records:
        con.execute(
            """
            INSERT INTO dim_station (station_id, name, address, lat, lon, capacity, first_seen_at, last_seen_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (station_id) DO UPDATE SET
                name = excluded.name,
                address = excluded.address,
                lat = excluded.lat,
                lon = excluded.lon,
                capacity = excluded.capacity,
                last_seen_at = excluded.last_seen_at
            """,
            [r.station_id, r.name, r.address, r.lat, r.lon, r.capacity, now, now],
        )  # this allows us to upsert the station information, updating the last_seen_at timestamp if the station already exists. This ensures idempotency.


def load_fct_station_status(
    con: duckdb.DuckDBPyConnection,
    records: list[StationStatus],
    run_id: str,
    now: datetime,
) -> None:
    rows = []
    for r in records:
        capacity_row = con.execute(
            "SELECT capacity FROM dim_station WHERE station_id = ?", [r.station_id]
        ).fetchone()
        capacity = capacity_row[0] if capacity_row else None
        occupancy_rate = (r.num_bikes_available / capacity) if capacity else None
        rows.append(
            (
                run_id,
                r.station_id,
                now,
                bool(r.is_installed),
                bool(r.can_rent),
                bool(r.can_return),
                r.num_bikes_available,
                r.num_docks_available,
                occupancy_rate,
            )
        )  # This does not check that the station_id exists in dim_station, so a potential improvement would be to add a check and log a warning if the station_id is not found in dim_station.
    if rows:
        con.executemany(
            """
            INSERT INTO fct_station_status
            (run_id, station_id, ingested_at, is_installed, can_rent, can_return,
             num_bikes_available, num_docks_available, occupancy_rate)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )


def load_fct_pass_sales(
    con: duckdb.DuckDBPyConnection, records: list[PassSale], run_id: str, now: datetime
) -> int:
    rows = [
        (
            r.transaction_id,
            r.user_id,
            r.pass_type,
            r.source,
            r.related_bike_station_id,
            r.price_nok,
            r.purchase_timestamp,
            now,
            run_id,
        )
        for r in records
    ]
    before = con.execute("SELECT count(*) FROM fct_pass_sales").fetchone()[0]
    if rows:
        con.executemany(
            """
            INSERT INTO fct_pass_sales
            (transaction_id, user_id, pass_type, source, related_station_id,
             price_nok, purchase_timestamp, ingested_at, run_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (transaction_id) DO NOTHING
            """,
            rows,
        )
    after = con.execute("SELECT count(*) FROM fct_pass_sales").fetchone()[0]
    inserted = after - before
    logger.info(
        "Pass sales: %s fetched, %s new, %s duplicates skipped",
        len(rows),
        inserted,
        len(rows) - inserted,
    )
    return inserted
