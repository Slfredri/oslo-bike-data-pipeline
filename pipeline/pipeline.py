"""Pipeline orchestration: extract -> transform -> load -> refresh marts."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from . import extract, load, metrics, transform

logger = logging.getLogger(__name__)


def run_once() -> dict:
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    now = datetime.now(timezone.utc)

    payloads = extract.extract_all(run_id)

    station_info_result = transform.transform_station_information(
        payloads["station_information"]
    )
    station_status_result = transform.transform_station_status(
        payloads["station_status"]
    )
    pass_sales_result = transform.transform_pass_sales(payloads["pass_sales"])

    con = (
        load.get_connection()
    )  # Initiate DB connection and create all 3 tables if they dont exist.
    try:
        load.load_dim_station(con, station_info_result.records, now)
        load.load_fct_station_status(con, station_status_result.records, run_id, now)
        inserted_sales = load.load_fct_pass_sales(
            con, pass_sales_result.records, run_id, now
        )
        metrics.create_marts(con)
    finally:
        con.close()

    summary = {
        "run_id": run_id,
        "stations_loaded": len(station_info_result.records),
        "status_snapshots_loaded": len(station_status_result.records),
        "pass_sales_fetched": pass_sales_result.total,
        "pass_sales_inserted": inserted_sales,
        "rejected_records": (
            station_info_result.rejected
            + station_status_result.rejected
            + pass_sales_result.rejected
        ),
    }
    logger.info("Pipeline run complete: %s", summary)
    return summary
