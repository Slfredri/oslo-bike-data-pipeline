"""Pydantic schemas describing the shape of a single record from each endpoint.

These translate the raw API payloads into the schema the pipeline expects.
Anything that does not match gets rejected (and logged) rather than silently corrupting downstream tables.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class StationInformation(BaseModel):
    station_id: str
    name: str
    address: str
    lat: float
    lon: float
    capacity: int


class StationStatus(BaseModel):
    station_id: str
    is_installed: int
    can_rent: int
    can_return: int
    num_bikes_available: int
    num_docks_available: int


class PassSale(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True
    )  # this lets us accept aliases for fields, e.g. RelatedBikeStationId. This is because the api returns PascalCase for that field.

    transaction_id: str
    user_id: str
    pass_type: str
    source: str
    related_bike_station_id: str | None = Field(
        default=None, alias="RelatedBikeStationId"
    )
    price_nok: float | None = None
    purchase_timestamp: datetime
