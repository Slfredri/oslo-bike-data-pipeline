"""Configuration for the pipeline."""

from __future__ import annotations

from pathlib import Path

# API
BASE_URL = "https://oslo-bike-api-13322556367.europe-west1.run.app"
REQUEST_TIMEOUT_SECONDS = 10

# Storage
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(str(PROJECT_ROOT / "data"))
RAW_DIR = DATA_DIR / "raw"
DB_PATH = Path(str(DATA_DIR / "warehouse.duckdb"))
