"""Execute DQ001-DQ012 rules driven by data_quality_rules.csv; write failures to dq_exception_report."""

import csv
import logging
import sqlite3
from datetime import date
from pathlib import Path
from typing import Callable

DB_PATH = Path("outputs/curated.sqlite")
INPUT_DIR = Path("input_data")
OUTPUT_DIR = Path("outputs")
DQ_RULES_PATH = INPUT_DIR / "data_quality_rules.csv"
EXCEPTIONS_CSV_PATH = OUTPUT_DIR / "exceptions.csv"
DQ_REPORT_PATH = OUTPUT_DIR / "data_quality_report.md"

logger = logging.getLogger(__name__)

# Country values (lowercased) that are non-standard variants requiring normalization to 'USA'
_NON_STANDARD_COUNTRIES = frozenset({"us", "united states"})

# Full US state names that should be abbreviated to two-letter codes.
# Kept here (rather than imported from transform.py) to keep the two modules decoupled.
_FULL_STATE_NAMES = frozenset({
    "alabama", "alaska", "arizona", "arkansas", "california", "colorado",
    "connecticut", "delaware", "florida", "georgia", "hawaii", "idaho",
    "illinois", "indiana", "iowa", "kansas", "kentucky", "louisiana",
    "maine", "maryland", "massachusetts", "michigan", "minnesota",
    "mississippi", "missouri", "montana", "nebraska", "nevada",
    "new hampshire", "new jersey", "new mexico", "new york",
    "north carolina", "north dakota", "ohio", "oklahoma", "oregon",
    "pennsylvania", "rhode island", "south carolina", "south dakota",
    "tennessee", "texas", "utah", "vermont", "virginia", "washington",
    "west virginia", "wisconsin", "wyoming",
})


def _load_rules(path: Path) -> dict:
    """Parse data_quality_rules.csv and return an ordered dict keyed by rule_id."""
    rules: dict = {}
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            rules[row["rule_id"]] = row
    logger.debug("Loaded %d DQ rules from %s", len(rules), path)
    return rules


def _insert_exception(
    conn: sqlite3.Connection,
    rule_id: str,
    dataset: str,
    record_key: str,
    severity: str,
    issue_description: str,
    suggested_action: str = "",
) -> None:
    """Insert one row into dq_exception_report for a single failing record."""
    conn.execute(
        "INSERT INTO dq_exception_report "
        "(rule_id, dataset, record_key, severity, issue_description, suggested_action) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (rule_id, dataset, record_key, severity, issue_description, suggested_action),
    )


def _check_dq001(conn: sqlite3.Connection, rule: dict) -> int:
    """
    DQ001: exact duplicate customer_ids exist in source data.

    Detects customer_ids that appear more than once in staging_customers (e.g. C006
    x2).  Cross-ID duplicates (different IDs, same person) are handled separately
    by DQ013.
    """
    count = 0
    rule_id, dataset, severity = rule["rule_id"], rule["dataset"], rule["severity"]
    suggested = rule.get("suggested_action", "")

    for cid, cnt in conn.execute(
        "SELECT customer_id, COUNT(*) AS cnt FROM staging_customers "
        "GROUP BY customer_id HAVING cnt > 1"
    ).fetchall():
        _insert_exception(
            conn, rule_id, dataset, cid, severity,
            f"customer_id {cid} appears {cnt} times in source (exact duplicate rows)",
            suggested,
        )
        count += 1
        logger.debug("DQ001: exact duplicate customer_id %s (%d rows)", cid, cnt)

    logger.info("DQ001: %d exceptions written", count)
    return count


def _check_dq002(conn: sqlite3.Connection, rule: dict) -> int:
    """
    DQ002: email is missing or absent for a customer.

    Flags dim_customer rows with NULL email. Missing emails are preserved as NULL
    (never fabricated) per the STTM rule; this check surfaces them for downstream attention.
    """
    count = 0
    rule_id, dataset, severity = rule["rule_id"], rule["dataset"], rule["severity"]
    suggested = rule.get("suggested_action", "")

    for (ckey,) in conn.execute(
        "SELECT customer_key FROM dim_customer WHERE email IS NULL"
    ).fetchall():
        _insert_exception(
            conn, rule_id, dataset, ckey, severity,
            f"Customer {ckey} has no email address on record",
            suggested,
        )
        count += 1
        logger.debug("DQ002: missing email for customer %s", ckey)

    logger.info("DQ002: %d exceptions written", count)
    return count


def _check_dq003(conn: sqlite3.Connection, rule: dict) -> int:
    """
    DQ003: country and state must be standardized.

    Scans all staging_customers rows for non-standard country variants ('US', 'United States')
    and full state names that should be two-letter codes.  A seen-set limits output to one
    exception per customer_id per field so that exact-duplicate staging rows (e.g. C006 x2
    with the same bad state) don't produce redundant flags.
    """
    count = 0
    rule_id, dataset, severity = rule["rule_id"], rule["dataset"], rule["severity"]
    # Tracks (customer_id, field) pairs already written to avoid duplicate exceptions
    seen: set = set()
    suggested = rule.get("suggested_action", "")

    for cid, raw_country, raw_state in conn.execute(
        "SELECT customer_id, country, state FROM staging_customers"
    ).fetchall():
        raw_c = (raw_country or "").strip()
        raw_s = (raw_state or "").strip()

        if raw_c.lower() in _NON_STANDARD_COUNTRIES:
            key = (cid, "country")
            if key not in seen:
                seen.add(key)
                _insert_exception(
                    conn, rule_id, dataset, cid, severity,
                    f"Customer {cid} country '{raw_c}' is a non-standard variant; should be 'USA'",
                    suggested,
                )
                count += 1
                logger.debug("DQ003: %s country '%s' needs normalization", cid, raw_c)

        if raw_s.lower() in _FULL_STATE_NAMES:
            key = (cid, "state")
            if key not in seen:
                seen.add(key)
                _insert_exception(
                    conn, rule_id, dataset, cid, severity,
                    f"Customer {cid} state '{raw_s}' is a full name; should use two-letter code",
                    suggested,
                )
                count += 1
                logger.debug("DQ003: %s state '%s' needs normalization", cid, raw_s)

    logger.info("DQ003: %d exceptions written", count)
    return count


def _check_dq004(conn: sqlite3.Connection, rule: dict) -> int:
    """
    DQ004: exact duplicate order_ids exist in source data.

    Detects order_ids appearing more than once in staging_orders (O1018 appears twice).
    Transform already retains only the first occurrence; this check records the
    raw-data violation for traceability.
    """
    count = 0
    rule_id, dataset, severity = rule["rule_id"], rule["dataset"], rule["severity"]
    suggested = rule.get("suggested_action", "")

    for oid, cnt in conn.execute(
        "SELECT order_id, COUNT(*) AS cnt FROM staging_orders "
        "GROUP BY order_id HAVING cnt > 1"
    ).fetchall():
        _insert_exception(
            conn, rule_id, dataset, oid, severity,
            f"order_id {oid} appears {cnt} times in source (exact duplicate rows)",
            suggested,
        )
        count += 1
        logger.debug("DQ004: duplicate order_id %s (%d rows)", oid, cnt)

    logger.info("DQ004: %d exceptions written", count)
    return count


def _check_dq005(conn: sqlite3.Connection, rule: dict) -> int:
    """
    DQ005: order references a customer_id not present in the customers dataset.

    Fact_order rows with NULL customer_key have an unresolvable customer_id.
    Joins back to staging_orders to surface the original invalid ID (e.g. O1019 → C999).
    """
    count = 0
    rule_id, dataset, severity = rule["rule_id"], rule["dataset"], rule["severity"]
    suggested = rule.get("suggested_action", "")

    for order_key, raw_cid in conn.execute(
        """SELECT fo.order_key, so.customer_id
           FROM fact_order fo
           JOIN staging_orders so ON fo.order_key = so.order_id
           WHERE fo.customer_key IS NULL"""
    ).fetchall():
        _insert_exception(
            conn, rule_id, dataset, order_key, severity,
            f"Order {order_key} references non-existent customer_id '{raw_cid}'",
            suggested,
        )
        count += 1
        logger.debug("DQ005: order %s → unknown customer %s", order_key, raw_cid)

    logger.info("DQ005: %d exceptions written", count)
    return count


def _check_dq006(conn: sqlite3.Connection, rule: dict) -> int:
    """
    DQ006: order references a product_id not present in the products dataset.

    Same pattern as DQ005 but for product FK violations (e.g. O1020 → P999).
    """
    count = 0
    rule_id, dataset, severity = rule["rule_id"], rule["dataset"], rule["severity"]
    suggested = rule.get("suggested_action", "")

    for order_key, raw_pid in conn.execute(
        """SELECT fo.order_key, so.product_id
           FROM fact_order fo
           JOIN staging_orders so ON fo.order_key = so.order_id
           WHERE fo.product_key IS NULL"""
    ).fetchall():
        _insert_exception(
            conn, rule_id, dataset, order_key, severity,
            f"Order {order_key} references non-existent product_id '{raw_pid}'",
            suggested,
        )
        count += 1
        logger.debug("DQ006: order %s → unknown product %s", order_key, raw_pid)

    logger.info("DQ006: %d exceptions written", count)
    return count


def _check_dq007(conn: sqlite3.Connection, rule: dict) -> int:
    """
    DQ007: completed order has a non-positive quantity.

    Flags fact_order rows where order_status is 'completed' and quantity is NULL
    or <= 0.  The known offender is O1030 with quantity -1 and total -21.00.
    """
    count = 0
    rule_id, dataset, severity = rule["rule_id"], rule["dataset"], rule["severity"]
    suggested = rule.get("suggested_action", "")

    for order_key, qty, total in conn.execute(
        """SELECT order_key, quantity, gross_order_amount
           FROM fact_order
           WHERE LOWER(order_status) = 'completed'
             AND (quantity IS NULL OR quantity <= 0)"""
    ).fetchall():
        _insert_exception(
            conn, rule_id, dataset, order_key, severity,
            f"Completed order {order_key} has non-positive quantity {qty} "
            f"(gross total: {total})",
            suggested,
        )
        count += 1
        logger.debug("DQ007: order %s qty=%s total=%s", order_key, qty, total)

    logger.info("DQ007: %d exceptions written", count)
    return count


def _check_dq008(conn: sqlite3.Connection, rule: dict) -> int:
    """
    DQ008: stated order_total does not match quantity x unit_price.

    Uses the pre-computed order_amount_variance in fact_order.  A 0.01 tolerance
    avoids false positives from floating-point rounding.  Orders with NULL
    product_key have no calculated_order_amount and are skipped (already flagged
    by DQ006).
    """
    count = 0
    rule_id, dataset, severity = rule["rule_id"], rule["dataset"], rule["severity"]
    suggested = rule.get("suggested_action", "")

    for order_key, gross, calc, variance in conn.execute(
        """SELECT order_key, gross_order_amount, calculated_order_amount, order_amount_variance
           FROM fact_order
           WHERE order_amount_variance IS NOT NULL
             AND ABS(order_amount_variance) > 0.01"""
    ).fetchall():
        _insert_exception(
            conn, rule_id, dataset, order_key, severity,
            f"Order {order_key} stated total {gross} does not match computed "
            f"{calc} (variance: {variance})",
            suggested,
        )
        count += 1
        logger.debug(
            "DQ008: order %s gross=%s calc=%s variance=%s",
            order_key, gross, calc, variance
        )

    logger.info("DQ008: %d exceptions written", count)
    return count


def _check_dq009(conn: sqlite3.Connection, rule: dict) -> int:
    """
    DQ009: payment references an order_id not present in the orders dataset.

    Fact_payment rows with NULL order_key are orphan payments.  Joins to
    staging_payments to surface the original invalid order_id (e.g. PMT029 → O9999).
    """
    count = 0
    rule_id, dataset, severity = rule["rule_id"], rule["dataset"], rule["severity"]
    suggested = rule.get("suggested_action", "")

    for pmt_key, raw_oid in conn.execute(
        """SELECT fp.payment_key, sp.order_id
           FROM fact_payment fp
           JOIN staging_payments sp ON fp.payment_key = sp.payment_id
           WHERE fp.order_key IS NULL"""
    ).fetchall():
        _insert_exception(
            conn, rule_id, dataset, pmt_key, severity,
            f"Payment {pmt_key} references non-existent order_id '{raw_oid}'",
            suggested,
        )
        count += 1
        logger.debug("DQ009: payment %s → unknown order %s", pmt_key, raw_oid)

    logger.info("DQ009: %d exceptions written", count)
    return count


def _check_dq010(conn: sqlite3.Connection, rule: dict) -> int:
    """
    DQ010: settled payment amount differs from the completed order total.

    Joins settled fact_payment rows with completed fact_order rows and flags
    mismatches beyond 0.01.  Non-settled statuses (voided, refunded) are excluded —
    their amounts legitimately differ from the order total (e.g. PMT005 voided at
    0.00, PMT014 refunded at -59.99).
    """
    count = 0
    rule_id, dataset, severity = rule["rule_id"], rule["dataset"], rule["severity"]
    suggested = rule.get("suggested_action", "")

    for pmt_key, pmt_amt, order_key, order_amt in conn.execute(
        """SELECT fp.payment_key, fp.payment_amount, fo.order_key, fo.gross_order_amount
           FROM fact_payment fp
           JOIN fact_order fo ON fp.order_key = fo.order_key
           WHERE LOWER(fp.payment_status) = 'settled'
             AND LOWER(fo.order_status) = 'completed'
             AND ABS(fp.payment_amount - fo.gross_order_amount) > 0.01"""
    ).fetchall():
        _insert_exception(
            conn, rule_id, dataset, pmt_key, severity,
            f"Payment {pmt_key} settled amount {pmt_amt} does not match "
            f"completed order {order_key} total {order_amt}",
            suggested,
        )
        count += 1
        logger.debug(
            "DQ010: payment %s amount=%s vs order %s total=%s",
            pmt_key, pmt_amt, order_key, order_amt
        )

    logger.info("DQ010: %d exceptions written", count)
    return count


def _check_dq011(conn: sqlite3.Connection, rule: dict) -> int:
    """
    DQ011: ticket created_ts cannot be parsed to a valid timestamp.

    Fact_customer_issue rows with NULL created_date but a non-empty raw created_ts
    in staging indicate a parse failure (e.g. T010 has created_ts = 'bad_timestamp').
    """
    count = 0
    rule_id, dataset, severity = rule["rule_id"], rule["dataset"], rule["severity"]
    suggested = rule.get("suggested_action", "")

    for ticket_id, raw_ts in conn.execute(
        """SELECT fci.ticket_id, st.created_ts
           FROM fact_customer_issue fci
           JOIN staging_support_tickets st ON fci.ticket_id = st.ticket_id
           WHERE fci.created_date IS NULL
             AND st.created_ts IS NOT NULL
             AND TRIM(st.created_ts) != ''"""
    ).fetchall():
        _insert_exception(
            conn, rule_id, dataset, ticket_id, severity,
            f"Ticket {ticket_id} has unparseable created_ts: '{raw_ts}'",
            suggested,
        )
        count += 1
        logger.debug("DQ011: ticket %s unparseable ts '%s'", ticket_id, raw_ts)

    logger.info("DQ011: %d exceptions written", count)
    return count


def _check_dq012(conn: sqlite3.Connection, rule: dict) -> int:
    """
    DQ012: ticket references a customer_id not present in the customers dataset.

    Fact_customer_issue rows with NULL customer_key reference an unknown customer_id.
    Joins to staging_support_tickets to retrieve the original invalid ID (e.g. T005 → C999).
    """
    count = 0
    rule_id, dataset, severity = rule["rule_id"], rule["dataset"], rule["severity"]
    suggested = rule.get("suggested_action", "")

    for ticket_id, raw_cid in conn.execute(
        """SELECT fci.ticket_id, st.customer_id
           FROM fact_customer_issue fci
           JOIN staging_support_tickets st ON fci.ticket_id = st.ticket_id
           WHERE fci.customer_key IS NULL"""
    ).fetchall():
        _insert_exception(
            conn, rule_id, dataset, ticket_id, severity,
            f"Ticket {ticket_id} references non-existent customer_id '{raw_cid}'",
            suggested,
        )
        count += 1
        logger.debug("DQ012: ticket %s → unknown customer %s", ticket_id, raw_cid)

    logger.info("DQ012: %d exceptions written", count)
    return count


def _check_dq013(conn: sqlite3.Connection, rule: dict) -> int:
    """
    DQ013: different customer_ids resolve to the same person via name and contact-info matching.

    Reads id_crosswalk, which transform populated during the cross-ID deduplication
    pass (union-find on full_name + phone or email).  Each (old_id → canonical_id)
    entry is a confirmed cross-ID duplicate.
    """
    count = 0
    rule_id, dataset, severity = rule["rule_id"], rule["dataset"], rule["severity"]
    suggested = rule.get("suggested_action", "")

    for old_id, canonical_id in conn.execute(
        "SELECT old_customer_id, canonical_customer_id FROM id_crosswalk"
    ).fetchall():
        _insert_exception(
            conn, rule_id, dataset, old_id, severity,
            f"customer_id {old_id} resolves to the same person as canonical customer "
            f"{canonical_id} (matching full_name + phone or email)",
            suggested,
        )
        count += 1
        logger.debug("DQ013: cross-ID duplicate %s → canonical %s", old_id, canonical_id)

    logger.info("DQ013: %d exceptions written", count)
    return count


def _check_dq014(conn: sqlite3.Connection, rule: dict) -> int:
    """
    DQ014: order references a product with active_flag = 0 (discontinued product).

    Joins fact_order with dim_product and flags any order whose product_key maps to
    an inactive product.  Known offender: O1015 → P011.
    """
    count = 0
    rule_id, dataset, severity = rule["rule_id"], rule["dataset"], rule["severity"]
    suggested = rule.get("suggested_action", "")

    for order_key, product_key in conn.execute(
        """SELECT fo.order_key, fo.product_key
           FROM fact_order fo
           JOIN dim_product dp ON fo.product_key = dp.product_key
           WHERE dp.active_flag = 0"""
    ).fetchall():
        _insert_exception(
            conn, rule_id, dataset, order_key, severity,
            f"Order {order_key} references inactive product {product_key} (active_flag = 0)",
            suggested,
        )
        count += 1
        logger.debug("DQ014: order %s → inactive product %s", order_key, product_key)

    logger.info("DQ014: %d exceptions written", count)
    return count


def _export_exceptions_csv(conn: sqlite3.Connection, path: Path) -> int:
    """
    Write every row in dq_exception_report to a CSV file, recreating it on each run.

    Columns written match the table schema: rule_id, dataset, record_key, severity,
    issue_description, suggested_action.  Rows are ordered by rule_id then record_key
    for deterministic diffs.  Returns the number of data rows written.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = conn.execute(
        "SELECT rule_id, dataset, record_key, severity, issue_description, suggested_action "
        "FROM dq_exception_report ORDER BY rule_id, record_key"
    ).fetchall()
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "rule_id", "dataset", "record_key", "severity",
            "issue_description", "suggested_action",
        ])
        writer.writerows(rows)
    logger.info("Exported %d exception rows to %s", len(rows), path)
    return len(rows)


def _generate_dq_report(conn: sqlite3.Connection, rules: dict, path: Path) -> None:
    """
    Render a Markdown data-quality report to path.

    Three sections:
    1. Executive summary — generation date, totals.
    2. Summary table — one row per rule, with exception count.
    3. Per-rule detail — offending record_keys and issue descriptions.

    All values come from dq_exception_report and the rules dict; nothing is hard-coded.
    Rules with zero exceptions are listed in the summary table and shown as 'passed clean'
    in the detail section so readers can confirm a rule was actually executed.
    """
    rows = conn.execute(
        "SELECT rule_id, record_key, issue_description "
        "FROM dq_exception_report ORDER BY rule_id, record_key"
    ).fetchall()

    exceptions_by_rule: dict = {}
    for rule_id, record_key, issue_desc in rows:
        exceptions_by_rule.setdefault(rule_id, []).append((record_key, issue_desc))

    total = len(rows)
    triggered = sum(1 for r in rules if r in exceptions_by_rule)
    passed = len(rules) - triggered

    lines = [
        "# Data Quality Report",
        "",
        f"**Generated:** {date.today().isoformat()}  ",
        "**Rules source:** `input_data/data_quality_rules.csv`",
        "",
        "---",
        "",
        "## Summary",
        "",
        f"**{total} exception(s)** detected across **{len(rules)} rules** "
        f"({triggered} triggered, {passed} passed clean).",
        "",
        "| Rule ID | Dataset | Severity | Description | Exceptions |",
        "|---------|---------|----------|-------------|:----------:|",
    ]

    for rule_id, rule in rules.items():
        cnt = len(exceptions_by_rule.get(rule_id, []))
        lines.append(
            f"| {rule_id} | {rule['dataset']} | {rule['severity']} | "
            f"{rule['rule_description']} | {cnt} |"
        )

    lines += ["", "---", "", "## Rule Details", ""]

    for rule_id, rule in rules.items():
        exceptions = exceptions_by_rule.get(rule_id, [])
        cnt = len(exceptions)
        status = f"{cnt} exception(s)" if cnt else "passed clean"

        lines.append(f"### {rule_id} — {rule['rule_description']}")
        lines.append(
            f"**Dataset:** {rule['dataset']} | "
            f"**Severity:** {rule['severity']} | "
            f"**Status:** {status}"
        )
        lines.append("")

        if cnt == 0:
            lines.append("No exceptions — this rule passed.")
        else:
            lines.append("| Record Key | Issue Description |")
            lines.append("|------------|-------------------|")
            for record_key, issue_desc in exceptions:
                # Escape pipe characters so they don't break the Markdown table
                safe_desc = issue_desc.replace("|", "\\|")
                lines.append(f"| `{record_key}` | {safe_desc} |")

        suggested = rule.get("suggested_action", "")
        if suggested:
            lines += ["", f"**Suggested action:** {suggested}"]

        lines += ["", "---", ""]

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")
    logger.info(
        "Data quality report written to %s (%d rules, %d exceptions)",
        path, len(rules), total,
    )


# Maps each rule_id from data_quality_rules.csv to its check function.
_RULE_REGISTRY: dict[str, Callable[[sqlite3.Connection, dict], int]] = {
    "DQ001": _check_dq001,
    "DQ002": _check_dq002,
    "DQ003": _check_dq003,
    "DQ004": _check_dq004,
    "DQ005": _check_dq005,
    "DQ006": _check_dq006,
    "DQ007": _check_dq007,
    "DQ008": _check_dq008,
    "DQ009": _check_dq009,
    "DQ010": _check_dq010,
    "DQ011": _check_dq011,
    "DQ012": _check_dq012,
    "DQ013": _check_dq013,
    "DQ014": _check_dq014,
}


def run(conn: sqlite3.Connection) -> None:
    """
    Execute all DQ checks driven by data_quality_rules.csv and write failures to
    dq_exception_report.

    Dispatches each rule_id from the CSV to its registered check function, passing
    the full rule dict so functions read dataset/severity/suggested_action from the
    CSV (not hard-coded).  Rule IDs in the CSV with no matching registry entry are
    logged as warnings so that new rules can be staged in the CSV before their
    function is written.

    After all checks complete the results are flushed to two output files:
    - outputs/exceptions.csv  — full exception table as a flat CSV
    - outputs/data_quality_report.md — human-readable per-rule summary
    """
    logger.info("Starting quality_checks stage")

    rules = _load_rules(DQ_RULES_PATH)
    total = 0

    for rule_id, rule in rules.items():
        fn = _RULE_REGISTRY.get(rule_id)
        if fn is None:
            logger.warning("No check function registered for rule_id %s — skipping", rule_id)
            continue
        total += fn(conn, rule)

    conn.commit()
    _export_exceptions_csv(conn, EXCEPTIONS_CSV_PATH)
    _generate_dq_report(conn, rules, DQ_REPORT_PATH)
    logger.info("quality_checks stage complete — %d total exception rows written", total)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    if not DB_PATH.exists():
        raise FileNotFoundError(
            f"Database not found at {DB_PATH}. "
            "Run src/ingest.py and src/transform.py first."
        )
    with sqlite3.connect(DB_PATH) as conn:
        run(conn)
