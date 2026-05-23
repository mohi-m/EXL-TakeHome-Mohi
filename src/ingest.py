import csv
import json
import logging
import sqlite3
from pathlib import Path

DB_PATH = Path("outputs/curated.sqlite")
INPUT_DIR = Path("input_data")

logger = logging.getLogger(__name__)

CSV_SOURCES = [
    ("customers.csv", "staging_customers"),
    ("products.csv", "staging_products"),
    ("orders.csv", "staging_orders"),
    ("payments.csv", "staging_payments"),
]

JSONL_SOURCES = [
    ("support_tickets.jsonl", "staging_support_tickets"),
]


def _load_csv(conn: sqlite3.Connection, filename: str, table: str) -> int:
    """
    Read a CSV file and load it into a staging table with all columns typed as TEXT.

    Column names are discovered from the CSV header row at runtime, so no schema
    needs to be hard-coded here. The table is dropped and recreated on every run
    to keep re-runs idempotent without manual cleanup.

    No data cleaning or type casting is done — that responsibility belongs to
    transform.py, which applies the STTM rules.

    Returns the number of rows inserted.
    """
    path = INPUT_DIR / filename
    logger.info("Loading %s -> %s", filename, table)

    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        columns = list(reader.fieldnames)
        # Read all rows inside the open block so the file handle stays valid
        rows = [[row[c] for c in columns] for row in reader]

    logger.debug("%s: discovered columns %s", table, columns)

    # Build DDL dynamically from the discovered column names; every column is TEXT
    # so risky fields like order_total and order_ts are never auto-cast by SQLite
    cols_ddl = ", ".join(f'"{c}" TEXT' for c in columns)
    conn.execute(f'DROP TABLE IF EXISTS "{table}"')
    conn.execute(f'CREATE TABLE "{table}" ({cols_ddl})')

    # One placeholder per column; executemany batches all rows in a single statement
    placeholders = ", ".join("?" for _ in columns)
    conn.executemany(f'INSERT INTO "{table}" VALUES ({placeholders})', rows)

    logger.info("%s: inserted %d rows", table, len(rows))
    return len(rows)


def _load_jsonl(conn: sqlite3.Connection, filename: str, table: str) -> int:
    """
    Read a JSONL file (one JSON object per line) and load it into a staging table
    with all columns typed as TEXT.

    Keys are unioned across every record rather than taken from just the first line.
    This guards against sparse records where an optional field only appears mid-file,
    which would cause a KeyError when building later rows.

    Non-string JSON values (numbers, booleans) are coerced to str so the TEXT
    constraint is satisfied. JSON null maps to SQL NULL rather than the string "None".

    Returns the number of rows inserted.
    """
    path = INPUT_DIR / filename
    logger.info("Loading %s -> %s", filename, table)

    records = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:  # skip blank lines that may appear at end of file
                records.append(json.loads(line))

    if not records:
        logger.warning("%s: file is empty, staging table will have no rows", filename)
        return 0

    # Walk every record to collect the full set of keys in first-seen order.
    # Using a separate `seen` set avoids the O(n) cost of `columns.index()` checks.
    seen: set[str] = set()
    columns: list[str] = []
    for record in records:
        for k in record:
            if k not in seen:
                columns.append(k)
                seen.add(k)

    logger.debug("%s: discovered columns %s", table, columns)

    cols_ddl = ", ".join(f'"{c}" TEXT' for c in columns)
    conn.execute(f'DROP TABLE IF EXISTS "{table}"')
    conn.execute(f'CREATE TABLE "{table}" ({cols_ddl})')

    placeholders = ", ".join("?" for _ in columns)
    rows = [
        # r.get(c) returns None for missing keys (sparse records); preserve that as
        # SQL NULL rather than the string "None" by checking for None explicitly
        [str(r[c]) if r.get(c) is not None else None for c in columns]
        for r in records
    ]
    conn.executemany(f'INSERT INTO "{table}" VALUES ({placeholders})', rows)

    logger.info("%s: inserted %d rows", table, len(rows))
    return len(rows)


def run(conn: sqlite3.Connection) -> None:
    """
    Load all raw source files into staging tables and commit.

    Called by pipeline.py with a shared connection so the entire ingest stage
    runs in one transaction; the commit here finalises only the staging writes.
    """
    logger.info("Starting ingest stage")

    for filename, table in CSV_SOURCES:
        _load_csv(conn, filename, table)

    for filename, table in JSONL_SOURCES:
        _load_jsonl(conn, filename, table)

    conn.commit()
    logger.info("Ingest stage complete — all staging tables committed")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        run(conn)
