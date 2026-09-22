"""CLI entrypoint.

Usage:
    python -m pipeline.run
    python -m pipeline.run --iterations 5 --interval 30
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

if __package__ in (None, ""):
    # Executed directly as a script (e.g. `python pipeline/run.py` or an
    # IDE "Run/Debug Python File" action) instead of `python -m pipeline.run`,
    # so relative imports have no parent package to resolve against. Fall
    # back to putting the project root on sys.path and importing absolutely.
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from pipeline.pipeline import run_once
else:
    from .pipeline import run_once


def _configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Oslo bike share data pipeline")
    parser.add_argument(
        "--iterations",
        type=int,
        default=1,
        help="Number of pipeline runs. Use >1 to build up a station_status history "
        "without waiting for a real scheduler (e.g. cron).",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=10.0,
        help="Seconds to sleep between iterations when --iterations > 1.",
    )
    args = parser.parse_args()

    _configure_logging()

    for i in range(args.iterations):
        summary = run_once()
        print(summary)
        if i < args.iterations - 1:
            time.sleep(args.interval)


if __name__ == "__main__":
    main()
