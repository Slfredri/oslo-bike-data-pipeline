"""Raw payload -> validated record transformation (bronze -> silver).

Validation happens per-record: a single malformed record is quarantined
(logged and dropped) instead of failing the whole batch. This keeps the
pipeline resilient to the kind of partial data quality issues you see in
the pass_sales feed (e.g. null price_nok). This step does not handle business logic transformations: those belong in the next step (silver -> gold).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, ValidationError

from .models import PassSale, StationInformation, StationStatus

logger = logging.getLogger(__name__)


@dataclass
class TransformResult:
    records: list[Any]
    total: int
    rejected: int
    errors: list[str] = field(default_factory=list)


def _record_id(raw: dict) -> str:
    return str(raw.get("station_id") or raw.get("transaction_id") or "unknown")


def _transform_records(
    raw_records: list[dict], model: type[BaseModel], label: str
) -> TransformResult:
    records: list[Any] = []
    errors: list[str] = []
    for raw in raw_records:
        try:
            records.append(model.model_validate(raw))
        except ValidationError as exc:
            errors.append(str(exc))
            logger.warning(
                "Rejected invalid %s record (%s): %s", label, _record_id(raw), exc
            )
    return TransformResult(
        records=records, total=len(raw_records), rejected=len(errors), errors=errors
    )


def transform_station_information(payload: dict) -> TransformResult:
    return _transform_records(
        payload["data"]["stations"], StationInformation, "station_information"
    )


def transform_station_status(payload: dict) -> TransformResult:
    return _transform_records(
        payload["data"]["stations"], StationStatus, "station_status"
    )


def transform_pass_sales(payload: dict) -> TransformResult:
    return _transform_records(payload["data"], PassSale, "pass_sales")
