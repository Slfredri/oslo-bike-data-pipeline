"""Extract step: fetch raw payloads and land them, untouched, in the raw zone.

Storing the raw JSON (bronze layer) before any parsing/validation gives us
an audit trail and lets us replay/reprocess history if the transform logic
changes later, without needing to call the API again.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from . import api_client
from .config import RAW_DIR

logger = logging.getLogger(__name__)

ENDPOINTS = ("station_information", "station_status", "pass_sales")

_FETCHERS = {
    "station_information": api_client.fetch_station_information,
    "station_status": api_client.fetch_station_status,
    "pass_sales": api_client.fetch_pass_sales,
}


def _ingest_raw(endpoint: str, run_id: str, payload: dict) -> Path:
    endpoint_dir = RAW_DIR / endpoint
    endpoint_dir.mkdir(parents=True, exist_ok=True)
    path = endpoint_dir / f"{run_id}.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def extract_all(run_id: str) -> dict[str, dict]:
    """Fetch every endpoint and land the raw payload. Returns endpoint -> payload."""
    payloads: dict[str, dict] = {}
    for endpoint in ENDPOINTS:
        payload = _FETCHERS[endpoint]()
        _ingest_raw(endpoint, run_id, payload)
        payloads[endpoint] = payload
        logger.info("Landed raw payload for %s (run_id=%s)", endpoint, run_id)
    return payloads
