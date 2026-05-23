# Approach

## Architecture

The pipeline runs in four sequential stages:

1. **Ingest** (`src/ingest.py`): Load raw CSVs and JSONL into SQLite staging tables as-is.
2. **Transform** (`src/transform.py`): Apply STTM mapping rules to produce curated tables. Invalid FK rows are routed to an exceptions table rather than the curated model.
3. **Quality Checks** (`src/quality_checks.py`): Execute DQ001–DQ012 rules against curated tables and write failures to `outputs/exceptions.csv`.
4. **Reporting** (`src/reporting.py`): Run the five business-question queries and render all outputs to `outputs/`.

## Key Design Decisions

- **SQLite** chosen for zero-infrastructure local execution via Python's built-in `sqlite3` module (no extra dependencies).
- Mixed timestamp formats in `orders.csv` are normalized with `strptime` fallback parsing before loading into `fact_order`.
- Duplicate customers are resolved before FK linking so downstream tables reference a single canonical `customer_key`.
- Exception records are preserved (not dropped) so the report can surface them.
