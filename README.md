# Oslo Bike Data Pipeline

A proof-of-concept ELT pipeline for a fictional Oslo bike-share operator.
It pulls data from their REST API, lands it, validates it, and persists it
into a clean, query-able DuckDB warehouse. The repo also has a "how used is each
station?" metric.

## Architecture (medallion-inspired)

```
API endpoints: station_information / station_status / pass_sales
        │  extract.py  (requests + retry/backoff via tenacity)
        ▼
data/raw/<endpoint>/<run_id>.json        <- bronze: immutable landing zone
        │  transform.py  (pydantic per-record validation)
        ▼
DuckDB tables                             <- silver: typed, deduplicated
  dim_station          (upserted)
  fct_station_status   (append-only snapshot per run -> builds timeseries per station)
  fct_pass_sales        (append-only, deduplication on transaction_id)
        │  metrics.py  (SQL views)
        ▼
mart_station_utilization / mart_station_demand / mart_station_overview   <- gold
```

Each stage is a separate module (`extract.py`, `transform.py`, `load.py`,
`metrics.py`) orchestrated by `pipeline.py`, so any layer can be tested,
replaced, or re-run independently.

## Why this design

- **Raw zone (bronze).** The API is the operator's live system, not an
  archive. Landing the untouched JSON per run gives us an audit trail and
  lets us reprocess history later if the transform logic changes, without
  re-querying the API.
- **DuckDB as the warehouse.** It's a real embedded SQL engine (not a flat
  file), so for a POC it is a perfectly suitable choice, since it is persistent and queryable (warehouse is stored as a .duckdb file), and requires no infrastructure. Analysts can open `data/warehouse.duckdb` with any
  DuckDB client and run SQL directly. It
  is also easy to adapt it into a hosted warehouse
  (BigQuery/Snowflake/Postgres) later since the SQL is standard.
- **Per-record validation.** The
  `pass_sales` feed has some data quality issues (e.g. some
  records have `price_nok: null`). A single bad record shouldn't fail an
  entire pipeline run — it's logged and dropped, and the rest loads fine.
- **Idempotent loads.** `dim_station` is upserted by `station_id`.
  `fct_pass_sales` is deduplicated by `transaction_id` (`ON CONFLICT DO
  NOTHING`), so re-running the pipeline never double-counts a sale.
- **`station_status` is a live snapshot, not history** — the API has no
  time dimension for it. The pipeline turns it into a time series itself:
  every run appends one row per station to `fct_station_status` with its
  own `ingested_at`. Run the pipeline repeatedly (see below) to build up
  a real history to compute utilization over time.
- **Gold layer as SQL views**, not materialized tables, so they're always
  current relative to whatever has been loaded, with no separate refresh
  step to forget.

## The usage metric

"How much is a station used" is answered from two angles, joined into the
`mart_station_overview` view:

1. **Operational utilization**, from `station_status` timeseries:
   - `avg_occupancy_rate` — average `bikes_available / capacity`.
   - `pct_time_stockout` — percentage of snapshots with **0 bikes available**
     (a stronger demand signal than occupancy alone: it means people
     wanted a bike and couldn't get one).
   - `pct_time_full` — percentage of snapshots with **0 free docks** (unmet
     return demand).
2. **Commercial demand**, from `pass_sales`: count and revenue of sales
  for a station via `RelatedBikeStationId`

`mart_station_overview` is sorted by `pct_time_stockout` descending, so
the first rows are the stations most worth prioritizing for a new/expanded
station nearby.

## Setup

Requires Python 3.10+.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Running

Single run (one snapshot of `station_status`, a fresh batch of `pass_sales`):

```bash
python -m pipeline.run
```

To build up real `station_status` history without waiting for a real
scheduler, run it a few times with a delay between calls:

```bash
python -m pipeline.run --iterations 5 --interval 30
```

In production this would instead be a scheduled job invoking the same `run_once()`
function every few minutes.

## Querying the result

```bash
python -c "
import duckdb
con = duckdb.connect('data/warehouse.duckdb')
con.sql('SELECT * FROM mart_station_overview').show()
"
```



## Tests

Transform and metrics logic are tested against static fixtures / an
in-memory DuckDB instance, no API calls. Run:

```bash
pytest
```

## Assumptions & limitations (POC scope)

- `pass_sales` is dynamic/random on each call, so it's treated as an
  ever-growing stream of new transactions rather than a fixed dataset.
- Rows with invalid/missing required fields are dropped and logged rather
  than crashing the run; `rejected_records` is reported in the run summary
  for monitoring.
- No orchestration, containerization, or CI is included, to keep the
  submission focused — the natural next steps would be: a Dockerfile +
  scheduled job/orchestrator, a  dbt layer instead of hard-coded SQL
  views once the transformation logic grows, alerting on the
  `rejected_records` count, and a BI tool
  pointed at the DuckDB (or a migrated hosted warehouse) for stakeholders.