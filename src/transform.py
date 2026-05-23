"""Apply STTM rules to produce dim_customer, dim_product, fact_order, fact_payment, fact_customer_issue."""

import csv
import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

DB_PATH = Path("outputs/curated.sqlite")
INPUT_DIR = Path("input_data")
STTM_PATH = INPUT_DIR / "sttm_target_mapping.csv"

logger = logging.getLogger(__name__)

# Full US state name → two-letter abbreviation
STATE_MAP = {
    "alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR",
    "california": "CA", "colorado": "CO", "connecticut": "CT", "delaware": "DE",
    "florida": "FL", "georgia": "GA", "hawaii": "HI", "idaho": "ID",
    "illinois": "IL", "indiana": "IN", "iowa": "IA", "kansas": "KS",
    "kentucky": "KY", "louisiana": "LA", "maine": "ME", "maryland": "MD",
    "massachusetts": "MA", "michigan": "MI", "minnesota": "MN", "mississippi": "MS",
    "missouri": "MO", "montana": "MT", "nebraska": "NE", "nevada": "NV",
    "new hampshire": "NH", "new jersey": "NJ", "new mexico": "NM", "new york": "NY",
    "north carolina": "NC", "north dakota": "ND", "ohio": "OH", "oklahoma": "OK",
    "oregon": "OR", "pennsylvania": "PA", "rhode island": "RI", "south carolina": "SC",
    "south dakota": "SD", "tennessee": "TN", "texas": "TX", "utah": "UT",
    "vermont": "VT", "virginia": "VA", "washington": "WA", "west virginia": "WV",
    "wisconsin": "WI", "wyoming": "WY",
}

# Datetime-with-time formats before date-only so strptime never partially matches
# e.g. "2025-03-01 10:15:00" won't be cut to just the date portion
TIMESTAMP_FORMATS = [
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%dT%H:%M:%SZ",  # ISO 8601 with Z suffix (orders.csv)
    "%Y-%m-%dT%H:%M:%S",   # ISO 8601 without Z (support_tickets.jsonl)
    "%Y-%m-%d %H:%M",      # most orders use this (no seconds)
    "%m/%d/%Y %H:%M",
    "%Y/%m/%d %H:%M",
    "%m-%d-%Y %H:%M",
    "%Y-%m-%d",
    "%m/%d/%Y",
    "%Y/%m/%d",
    "%m-%d-%Y",
]

# STTM columns that need REAL storage for arithmetic in reporting queries
_REAL_COLS = frozenset({
    "unit_price", "gross_order_amount", "calculated_order_amount",
    "order_amount_variance", "payment_amount",
})
# STTM columns that need INTEGER storage
_INTEGER_COLS = frozenset({"duplicate_resolution_flag", "active_flag", "quantity"})


def parse_timestamp(value: Optional[str]) -> Optional[str]:
    """
    Try each known mixed-format pattern and return an ISO date string (YYYY-MM-DD).
    Returns None when value is absent or does not match any pattern — callers
    treat None as a DQ011/DQ flag rather than a hard error.
    """
    if not value:
        return None
    v = value.strip()
    for fmt in TIMESTAMP_FORMATS:
        try:
            return datetime.strptime(v, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def normalize_country(value: Optional[str]) -> Optional[str]:
    """Collapse 'USA', 'US', and 'United States' to the canonical 'USA'; pass other values through."""
    if not value:
        return value
    return "USA" if value.strip().upper() in {"USA", "US", "UNITED STATES"} else value.strip()


def normalize_state(value: Optional[str]) -> Optional[str]:
    """
    Map full US state names to two-letter codes using STATE_MAP.
    Values that are already two characters are uppercased and returned as-is.
    Unrecognised longer strings (e.g. non-US territory names) are returned unchanged.
    """
    if not value:
        return value
    v = value.strip()
    code = STATE_MAP.get(v.lower())
    if code:
        return code
    # Already looks like an abbreviation
    if len(v) <= 2:
        return v.upper()
    return v


def to_decimal(value: Optional[str]) -> Optional[float]:
    """Cast a string representation of a number to float; return None when absent or non-numeric."""
    if not value:
        return None
    try:
        return float(value.strip().replace("$", "").replace(",", ""))
    except (ValueError, AttributeError):
        return None


def _completeness(row: dict) -> int:
    """Count non-empty, non-None fields; used to prefer the most-complete row when deduplicating."""
    return sum(1 for v in row.values() if v is not None and v != "")


def load_sttm(path: Path) -> dict:
    """
    Parse sttm_target_mapping.csv and return a dict keyed by target_table, each
    value being an ordered list of column-mapping dicts (preserving CSV row order).
    This drives DDL generation so curated schemas are never hard-coded in pipeline code.
    """
    tables: dict = {}
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            tables.setdefault(row["target_table"], []).append(row)
    logger.debug(
        "STTM loaded: %d tables, %d total mappings",
        len(tables),
        sum(len(v) for v in tables.values()),
    )
    return tables


def _create_curated_tables(conn: sqlite3.Connection, sttm: dict) -> None:
    """
    Drop and recreate all curated tables (plus id_crosswalk) using the column lists
    from the STTM.  Column types default to TEXT; _REAL_COLS and _INTEGER_COLS
    override to REAL/INTEGER where arithmetic is needed in reporting queries.
    dq_exception_report has no primary key because multiple exceptions share the
    same rule_id.
    """
    for table, mappings in sttm.items():
        conn.execute(f'DROP TABLE IF EXISTS "{table}"')

        if table == "dq_exception_report":
            # No PK — this table accumulates one row per failing record per rule
            cols_ddl = ", ".join(f'"{m["target_column"]}" TEXT' for m in mappings)
            conn.execute(f'CREATE TABLE "{table}" ({cols_ddl})')
        else:
            cols_ddl_parts = []
            for i, m in enumerate(mappings):
                col = m["target_column"]
                if col in _REAL_COLS:
                    col_type = "REAL"
                elif col in _INTEGER_COLS:
                    col_type = "INTEGER"
                else:
                    col_type = "TEXT"
                pk_clause = " PRIMARY KEY" if i == 0 else ""
                cols_ddl_parts.append(f'"{col}" {col_type}{pk_clause}')
            conn.execute(f'CREATE TABLE "{table}" ({", ".join(cols_ddl_parts)})')

        logger.debug(
            "Created curated table %s with columns: %s",
            table,
            [m["target_column"] for m in mappings],
        )

    # id_crosswalk is not in the STTM but is needed for FK remapping in fact builders
    conn.execute("DROP TABLE IF EXISTS id_crosswalk")
    conn.execute(
        """CREATE TABLE id_crosswalk (
               old_customer_id      TEXT PRIMARY KEY,
               canonical_customer_id TEXT NOT NULL
           )"""
    )
    logger.info("All curated tables and id_crosswalk created")


def _build_dim_customer(conn: sqlite3.Connection) -> dict:
    """
    Build dim_customer with two-pass deduplication and return the in-memory
    crosswalk dict {old_customer_id: canonical_customer_id}.

    Pass 1 — exact customer_id duplicates:
        Keep the most-complete row (most non-empty fields) for each customer_id.
        When completeness is tied, first occurrence wins.

    Pass 2 — cross-ID duplicates (union-find):
        Link any two surviving rows whose normalised full_name matches AND whose
        non-empty phone or non-empty email matches.  Phone-only matching is
        intentionally excluded: C016 Henry Martin shares a phone with C001 Ava Patel
        but they are distinct people — name must also agree.
        The lexicographically smallest customer_id in each cluster becomes the
        canonical customer_key; the others are entered into id_crosswalk and
        excluded from dim_customer.
    """
    cur = conn.execute("SELECT * FROM staging_customers")
    cols = [d[0] for d in cur.description]
    all_rows = [dict(zip(cols, row)) for row in cur.fetchall()]

    # --- Pass 1: collapse exact customer_id duplicates ---
    by_id: dict = {}
    for row in all_rows:
        cid = row["customer_id"]
        if cid not in by_id:
            by_id[cid] = row
        elif _completeness(row) > _completeness(by_id[cid]):
            logger.debug("DQ001 pass-1: %s — replacing with more-complete row", cid)
            by_id[cid] = row
        else:
            logger.debug("DQ001 pass-1: %s — discarding less-complete duplicate", cid)

    logger.info(
        "dim_customer pass 1: %d raw rows → %d after exact-id dedup",
        len(all_rows),
        len(by_id),
    )

    # --- Pass 2: cross-ID duplicate detection via union-find ---
    ids = list(by_id.keys())
    parent = {cid: cid for cid in ids}

    def find(x: str) -> str:
        """Path-compressing find for the union-find structure."""
        while parent[x] != x:
            parent[x] = parent[parent[x]]  # path compression halves chain length
            x = parent[x]
        return x

    def union(a: str, b: str) -> None:
        """Merge two clusters; lexicographically smallest id becomes root (canonical)."""
        ra, rb = find(a), find(b)
        if ra == rb:
            return
        if ra < rb:
            parent[rb] = ra
        else:
            parent[ra] = rb

    def _norm_name(row: dict) -> str:
        fn = (row.get("first_name") or "").strip().lower()
        ln = (row.get("last_name") or "").strip().lower()
        return f"{fn} {ln}"

    def _norm_email(row: dict) -> Optional[str]:
        e = (row.get("email") or "").strip().lower()
        return e or None

    def _norm_phone(row: dict) -> Optional[str]:
        p = (row.get("phone") or "").strip()
        return p or None

    for i, cid_a in enumerate(ids):
        for cid_b in ids[i + 1:]:
            row_a, row_b = by_id[cid_a], by_id[cid_b]
            if _norm_name(row_a) != _norm_name(row_b):
                continue
            phone_a, phone_b = _norm_phone(row_a), _norm_phone(row_b)
            email_a, email_b = _norm_email(row_a), _norm_email(row_b)
            phone_match = phone_a and phone_b and phone_a == phone_b
            email_match = email_a and email_b and email_a == email_b
            if phone_match or email_match:
                match_detail = f"phone {phone_a}" if phone_match else f"email {email_a}"
                logger.warning(
                    "DQ001 pass-2: cross-ID duplicate — %s and %s share name '%s' + %s",
                    cid_a,
                    cid_b,
                    _norm_name(row_a),
                    match_detail,
                )
                union(cid_a, cid_b)

    # Build crosswalk: any id whose canonical root differs from itself is non-canonical
    crosswalk: dict = {}
    for cid in ids:
        canonical = find(cid)
        if cid != canonical:
            crosswalk[cid] = canonical

    conn.executemany(
        "INSERT INTO id_crosswalk (old_customer_id, canonical_customer_id) VALUES (?, ?)",
        list(crosswalk.items()),
    )
    logger.info("id_crosswalk: %d non-canonical mappings persisted", len(crosswalk))

    # --- Insert one dim_customer row per canonical id ---
    non_canonical = set(crosswalk.keys())
    dim_rows = []
    for cid, row in by_id.items():
        if cid in non_canonical:
            continue  # merged into a canonical sibling

        # 1 if this canonical row absorbed at least one other customer_id
        is_merged = any(find(m) == cid for m in non_canonical)

        full_name = (
            f"{(row.get('first_name') or '').strip()} "
            f"{(row.get('last_name') or '').strip()}"
        ).strip()
        email_raw = (row.get("email") or "").strip().lower()

        dim_rows.append((
            cid,                                  # customer_key
            full_name,                            # full_name
            email_raw or None,                    # email (NULL when absent, never fabricated)
            row.get("phone") or None,             # phone
            normalize_country(row.get("country")),  # standard_country
            normalize_state(row.get("state")),    # standard_state
            parse_timestamp(row.get("signup_date")),  # signup_date
            row.get("loyalty_tier"),              # loyalty_tier
            1 if is_merged else 0,                # duplicate_resolution_flag
        ))

    conn.executemany(
        """INSERT INTO dim_customer
               (customer_key, full_name, email, phone,
                standard_country, standard_state, signup_date,
                loyalty_tier, duplicate_resolution_flag)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        dim_rows,
    )
    logger.info("dim_customer: inserted %d canonical rows", len(dim_rows))
    return crosswalk


def _build_dim_product(conn: sqlite3.Connection) -> None:
    """
    Build dim_product from staging_products.  No deduplication is required
    (product_ids are unique in the source).  Casts unit_price to REAL and
    active_flag to INTEGER (defaulting to 1 when the field is absent or unparseable).
    """
    cur = conn.execute("SELECT * FROM staging_products")
    cols = [d[0] for d in cur.description]
    rows = [dict(zip(cols, row)) for row in cur.fetchall()]

    dim_rows = []
    for row in rows:
        price = to_decimal(row.get("unit_price"))
        raw_flag = (row.get("active_flag") or "").strip().upper()
        if raw_flag in ("1", "Y", "YES", "TRUE"):
            active = 1
        elif raw_flag in ("0", "N", "NO", "FALSE"):
            active = 0
        else:
            # Unrecognised value — default active to avoid silent data loss
            active = 1
            if raw_flag:
                logger.warning("dim_product: %s has unrecognised active_flag '%s', defaulting to 1", row.get("product_id"), raw_flag)

        dim_rows.append((
            row["product_id"],   # product_key
            row["product_name"], # product_name
            row["category"],     # category
            price,               # unit_price (REAL)
            active,              # active_flag (INTEGER)
        ))

    conn.executemany(
        "INSERT INTO dim_product (product_key, product_name, category, unit_price, active_flag) VALUES (?, ?, ?, ?, ?)",
        dim_rows,
    )
    logger.info("dim_product: inserted %d rows", len(dim_rows))


def _build_fact_order(conn: sqlite3.Connection, crosswalk: dict) -> None:
    """
    Build fact_order from staging_orders.

    - Deduplicates order_id (first occurrence wins; quality_checks.py flags DQ004).
    - Remaps customer_id through the crosswalk so merged customers link to one key.
    - Validates customer_key and product_key against the dim tables; sets NULL for
      invalid references (no silent drops — quality_checks.py flags DQ005/DQ006).
    - computed calculated_order_amount = quantity × dim_product.unit_price.
    - computed order_amount_variance = gross_order_amount − calculated_order_amount.
    """
    cur = conn.execute("SELECT * FROM staging_orders")
    cols = [d[0] for d in cur.description]
    rows = [dict(zip(cols, row)) for row in cur.fetchall()]

    valid_customers = {
        r[0] for r in conn.execute("SELECT customer_key FROM dim_customer").fetchall()
    }
    product_prices: dict = {
        r[0]: r[1]
        for r in conn.execute("SELECT product_key, unit_price FROM dim_product").fetchall()
    }

    seen_orders: set = set()
    fact_rows = []

    for row in rows:
        oid = row["order_id"]
        if oid in seen_orders:
            # Duplicate order_id — keep only the first occurrence
            logger.debug("DQ004: duplicate order_id %s skipped on second occurrence", oid)
            continue
        seen_orders.add(oid)

        raw_cid = row.get("customer_id")
        canonical_cid = crosswalk.get(raw_cid, raw_cid)
        if canonical_cid not in valid_customers:
            logger.warning("DQ005: order %s references unknown customer_id %s", oid, raw_cid)
            customer_key = None
        else:
            customer_key = canonical_cid

        raw_pid = row.get("product_id")
        if raw_pid not in product_prices:
            logger.warning("DQ006: order %s references unknown product_id %s", oid, raw_pid)
            product_key = None
        else:
            product_key = raw_pid

        gross = to_decimal(row.get("order_total"))

        qty_raw = row.get("quantity")
        try:
            qty = int(qty_raw) if qty_raw is not None else None
        except (ValueError, TypeError):
            qty = None

        unit_price = product_prices.get(product_key) if product_key else None
        if qty is not None and unit_price is not None:
            calculated = round(qty * unit_price, 2)
        else:
            calculated = None

        if gross is not None and calculated is not None:
            variance = round(gross - calculated, 2)
        else:
            variance = None

        fact_rows.append((
            oid,                                          # order_key
            customer_key,                                 # customer_key (NULL if invalid)
            product_key,                                  # product_key (NULL if invalid)
            parse_timestamp(row.get("order_ts")),         # order_date
            qty,                                          # quantity
            row.get("order_status"),                      # order_status
            normalize_state(row.get("shipping_state")),   # shipping_state
            gross,                                        # gross_order_amount
            calculated,                                   # calculated_order_amount
            variance,                                     # order_amount_variance
        ))

    conn.executemany(
        """INSERT INTO fact_order
               (order_key, customer_key, product_key, order_date,
                quantity, order_status, shipping_state,
                gross_order_amount, calculated_order_amount, order_amount_variance)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        fact_rows,
    )
    logger.info("fact_order: inserted %d rows", len(fact_rows))


def _build_fact_payment(conn: sqlite3.Connection) -> None:
    """
    Build fact_payment from staging_payments.

    order_key is validated against fact_order; orphan payments (e.g. PMT029 →
    O9999) receive a NULL order_key and are NOT dropped (quality_checks.py flags DQ009).
    """
    cur = conn.execute("SELECT * FROM staging_payments")
    cols = [d[0] for d in cur.description]
    rows = [dict(zip(cols, row)) for row in cur.fetchall()]

    valid_orders = {
        r[0] for r in conn.execute("SELECT order_key FROM fact_order").fetchall()
    }

    fact_rows = []
    for row in rows:
        raw_oid = row.get("order_id")
        if raw_oid not in valid_orders:
            logger.warning(
                "DQ009: payment %s references unknown order_id %s",
                row.get("payment_id"),
                raw_oid,
            )
            order_key = None
        else:
            order_key = raw_oid

        fact_rows.append((
            row["payment_id"],                        # payment_key
            order_key,                                # order_key (NULL if orphan)
            parse_timestamp(row.get("payment_ts")),   # payment_date
            row.get("payment_method"),                # payment_method
            row.get("payment_status"),                # payment_status
            to_decimal(row.get("amount")),            # payment_amount
        ))

    conn.executemany(
        """INSERT INTO fact_payment
               (payment_key, order_key, payment_date,
                payment_method, payment_status, payment_amount)
           VALUES (?, ?, ?, ?, ?, ?)""",
        fact_rows,
    )
    logger.info("fact_payment: inserted %d rows", len(fact_rows))


def _build_fact_customer_issue(conn: sqlite3.Connection, crosswalk: dict) -> None:
    """
    Build fact_customer_issue from staging_support_tickets.

    customer_key is resolved through the crosswalk then validated against dim_customer;
    tickets referencing unknown customer IDs receive NULL customer_key (DQ012, no silent drop).
    Unparseable created_ts values are set to NULL (DQ011 — flagged by quality_checks.py).
    """
    cur = conn.execute("SELECT * FROM staging_support_tickets")
    cols = [d[0] for d in cur.description]
    rows = [dict(zip(cols, row)) for row in cur.fetchall()]

    valid_customers = {
        r[0] for r in conn.execute("SELECT customer_key FROM dim_customer").fetchall()
    }

    fact_rows = []
    for row in rows:
        raw_cid = row.get("customer_id")
        canonical_cid = crosswalk.get(raw_cid, raw_cid)
        if canonical_cid not in valid_customers:
            logger.warning(
                "DQ012: ticket %s references unknown customer_id %s",
                row.get("ticket_id"),
                raw_cid,
            )
            customer_key = None
        else:
            customer_key = canonical_cid

        raw_ts = row.get("created_ts")
        created_date = parse_timestamp(raw_ts)
        if created_date is None and raw_ts:
            logger.warning(
                "DQ011: ticket %s has unparseable created_ts '%s'",
                row.get("ticket_id"),
                raw_ts,
            )

        fact_rows.append((
            row["ticket_id"],      # ticket_id
            customer_key,          # customer_key (NULL if unresolvable)
            created_date,          # created_date (NULL if unparseable)
            row.get("channel"),    # channel
            row.get("category"),   # issue_category
            row.get("sentiment"),  # sentiment
            row.get("description"),# description
        ))

    conn.executemany(
        """INSERT INTO fact_customer_issue
               (ticket_id, customer_key, created_date,
                channel, issue_category, sentiment, description)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        fact_rows,
    )
    logger.info("fact_customer_issue: inserted %d rows", len(fact_rows))


def run(conn: sqlite3.Connection) -> None:
    """
    Transform all staging tables into curated tables following STTM rules.

    Orchestration order is significant: dim tables must be fully built before
    fact builders run, because fact builders validate FKs against the dims.
    The crosswalk returned by _build_dim_customer is threaded into every
    fact builder that references customer_id.
    """
    logger.info("Starting transform stage")

    sttm = load_sttm(STTM_PATH)
    _create_curated_tables(conn, sttm)

    crosswalk = _build_dim_customer(conn)
    _build_dim_product(conn)
    _build_fact_order(conn, crosswalk)
    _build_fact_payment(conn)
    _build_fact_customer_issue(conn, crosswalk)

    conn.commit()
    logger.info("Transform stage complete — all curated tables committed")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    if not DB_PATH.exists():
        raise FileNotFoundError(
            f"Database not found at {DB_PATH}. Run src/ingest.py first."
        )
    with sqlite3.connect(DB_PATH) as conn:
        run(conn)
