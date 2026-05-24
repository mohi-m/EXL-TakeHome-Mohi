"""Entry point: orchestrates ingest → transform → quality_checks → reporting."""

import logging
import sqlite3
from pathlib import Path

import ingest
import quality_checks
import reporting
import transform

DB_PATH = Path("outputs/curated.sqlite")

logger = logging.getLogger(__name__)


def main() -> None:
    """
    Run the full OmniRetail pipeline end-to-end.

    The database is deleted and recreated on every run so reruns are fully
    idempotent — there is no incremental state to manage.  Stage order is fixed:
    ingest must precede transform (staging tables must exist), transform must
    precede quality_checks and reporting (curated tables must exist).
    """
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    # Always start from a clean DB so repeated runs produce identical outputs
    if DB_PATH.exists():
        DB_PATH.unlink()
        logger.info("Removed existing database at %s", DB_PATH)

    with sqlite3.connect(DB_PATH) as conn:
        ingest.run(conn)
        transform.run(conn)
        quality_checks.run(conn)
        reporting.run(conn)

    logger.info("Pipeline complete — outputs written to %s/", DB_PATH.parent)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    main()
