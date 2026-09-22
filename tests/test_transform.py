import json
from pathlib import Path

from pipeline.transform import (
    transform_pass_sales,
    transform_station_information,
    transform_station_status,
)

FIXTURES = Path(__file__).parent / "fixtures"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


def test_transform_station_information_rejects_invalid_records():
    result = transform_station_information(_load("station_information.json"))

    # 3 raw records in the fixture, 1 is missing required fields (address/lat/lon)
    assert result.total == 3
    assert len(result.records) == 2
    assert result.rejected == 1
    assert result.records[0].station_id == "128"


def test_transform_station_status_all_valid():
    result = transform_station_status(_load("station_status.json"))

    assert result.total == 3
    assert len(result.records) == 3
    assert result.rejected == 0


def test_transform_pass_sales_handles_nulls():
    result = transform_pass_sales(_load("pass_sales.json"))

    assert len(result.records) == 3
    by_id = {r.transaction_id: r for r in result.records}

    assert by_id["txn_1"].related_bike_station_id is None
    assert by_id["txn_2"].price_nok is None
    assert by_id["txn_3"].related_bike_station_id == "128"
