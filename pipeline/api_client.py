"""HTTP client for the Oslo Bike Share API with retry/backoff.

Kept intentionally dumb: it only knows how to fetch raw JSON payloads.
Validation and shaping happen downstream in transform.py.
"""

from __future__ import annotations

import logging

import requests
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from .config import BASE_URL, REQUEST_TIMEOUT_SECONDS

logger = logging.getLogger(__name__)


@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    retry=retry_if_exception_type(requests.RequestException),
)
def _get(endpoint: str) -> dict:
    url = f"{BASE_URL.rstrip('/')}/{endpoint.lstrip('/')}"
    logger.info("Fetching %s", url)
    response = requests.get(url, timeout=REQUEST_TIMEOUT_SECONDS)
    response.raise_for_status()
    return response.json()


def fetch_station_information() -> dict:
    return _get("station_information")


def fetch_station_status() -> dict:
    return _get("station_status")


def fetch_pass_sales() -> dict:
    return _get("pass_sales")
