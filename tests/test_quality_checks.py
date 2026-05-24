"""
Lightweight data-quality validation against the curated SQLite database.

Four assertion groups:
  1. Row counts    — staging raw totals are accounted for by curated rows + dedup exceptions.
  2. Referential   — FK integrity: non-null foreign keys resolve to valid parent rows.
  3. Amounts       — domain-logic boundaries: aggregations and sign constraints.
  4. Parsing       — primary-key completeness, schema conformance, and type casting.

Run with:
    pytest tests/test_quality_checks.py -v

The database must be populated before tests run:
    python3 src/pipeline.py
"""

import logging
import sqlite3
from pathlib import Path

import pytest

DB_PATH = Path("outputs/curated.sqlite")

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Session fixture
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def conn():
    """
    Open a shared read-only connection to the curated database for the entire test session.

    Skips all tests if the database does not exist, directing the user to run the pipeline
    first.  Read-only URI mode prevents any accidental writes from test code.
    """
    if not DB_PATH.exists():
        pytest.skip(
            f"Database not found at {DB_PATH}. "
            "Run 'python3 src/pipeline.py' first to populate it."
        )
    logger.info("Opening test connection to %s", DB_PATH)
    with sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True) as c:
        yield c


# ---------------------------------------------------------------------------
# 1. Row counts
# ---------------------------------------------------------------------------

class TestRowCounts:
    """
    Verify that raw staging rows are fully accounted for across curated rows
    and deduplication exceptions.

    The pipeline removes rows only when deduplicating; FK-invalid rows are kept in
    curated tables with NULL foreign keys.  So for each entity the identity is:

        staging rows = curated rows + rows removed by dedup
    """

    def test_customer_row_accounting(self, conn):
        """
        20 staging customers = 18 canonical dim_customer rows
        + 1 exact-duplicate exception (DQ001, C006)
        + 1 cross-ID merge (id_crosswalk, C019 → C001).
        """
        staging = conn.execute("SELECT COUNT(*) FROM staging_customers").fetchone()[0]
        curated = conn.execute("SELECT COUNT(*) FROM dim_customer").fetchone()[0]
        # DQ001 exceptions count distinct customer_ids flagged as exact duplicates
        exact_dup_exc = conn.execute(
            "SELECT COUNT(*) FROM dq_exception_report WHERE rule_id = 'DQ001'"
        ).fetchone()[0]
        # id_crosswalk rows represent customers merged into a canonical sibling
        crosswalk = conn.execute("SELECT COUNT(*) FROM id_crosswalk").fetchone()[0]
        assert staging == curated + exact_dup_exc + crosswalk, (
            f"Customer accounting: {staging} staging ≠ "
            f"{curated} curated + {exact_dup_exc} DQ001 + {crosswalk} crosswalk"
        )

    def test_order_row_accounting(self, conn):
        """
        31 staging orders = 30 unique fact_order rows
        + 1 exact-duplicate exception (DQ004, O1018 appears twice).
        """
        staging = conn.execute("SELECT COUNT(*) FROM staging_orders").fetchone()[0]
        curated = conn.execute("SELECT COUNT(*) FROM fact_order").fetchone()[0]
        dup_exc = conn.execute(
            "SELECT COUNT(*) FROM dq_exception_report WHERE rule_id = 'DQ004'"
        ).fetchone()[0]
        assert staging == curated + dup_exc, (
            f"Order accounting: {staging} staging ≠ {curated} curated + {dup_exc} DQ004"
        )

    def test_product_row_count(self, conn):
        """Products have no deduplication — staging and dim_product counts must be equal."""
        staging = conn.execute("SELECT COUNT(*) FROM staging_products").fetchone()[0]
        curated = conn.execute("SELECT COUNT(*) FROM dim_product").fetchone()[0]
        assert staging == curated, (
            f"Product count mismatch: {staging} staging vs {curated} curated"
        )

    def test_payment_row_count(self, conn):
        """
        Payments have no deduplication — all staging rows appear in fact_payment.
        Orphan payments (PMT029) are retained with a NULL order_key rather than dropped.
        """
        staging = conn.execute("SELECT COUNT(*) FROM staging_payments").fetchone()[0]
        curated = conn.execute("SELECT COUNT(*) FROM fact_payment").fetchone()[0]
        assert staging == curated, (
            f"Payment count mismatch: {staging} staging vs {curated} curated"
        )

    def test_ticket_row_count(self, conn):
        """
        Support tickets have no deduplication — staging and fact_customer_issue counts
        must match.  Invalid FK tickets are kept with NULL customer_key.
        """
        staging = conn.execute("SELECT COUNT(*) FROM staging_support_tickets").fetchone()[0]
        curated = conn.execute("SELECT COUNT(*) FROM fact_customer_issue").fetchone()[0]
        assert staging == curated, (
            f"Ticket count mismatch: {staging} staging vs {curated} curated"
        )

    def test_exception_report_expected_total(self, conn):
        """
        dq_exception_report must contain at least 21 rows — one per known DQ violation
        (DQ001–DQ014, counting each flagged record individually).
        """
        total = conn.execute("SELECT COUNT(*) FROM dq_exception_report").fetchone()[0]
        assert total >= 21, (
            f"Expected ≥21 exception rows (one per known violation), got {total}"
        )


# ---------------------------------------------------------------------------
# 2. Referential checks
# ---------------------------------------------------------------------------

class TestReferentialChecks:
    """
    Validate FK relationships: non-null foreign keys in fact tables must resolve
    to a valid parent row.  Null FK values are the expected result for known
    invalid references (no silent drops).
    """

    def test_fact_order_customer_key_valid(self, conn):
        """Non-null customer_key in fact_order must point to an existing dim_customer row."""
        orphans = conn.execute(
            "SELECT COUNT(*) FROM fact_order "
            "WHERE customer_key IS NOT NULL "
            "  AND customer_key NOT IN (SELECT customer_key FROM dim_customer)"
        ).fetchone()[0]
        assert orphans == 0, (
            f"{orphans} fact_order rows have a non-null customer_key with no dim_customer parent"
        )

    def test_fact_order_product_key_valid(self, conn):
        """Non-null product_key in fact_order must point to an existing dim_product row."""
        orphans = conn.execute(
            "SELECT COUNT(*) FROM fact_order "
            "WHERE product_key IS NOT NULL "
            "  AND product_key NOT IN (SELECT product_key FROM dim_product)"
        ).fetchone()[0]
        assert orphans == 0, (
            f"{orphans} fact_order rows have a non-null product_key with no dim_product parent"
        )

    def test_fact_payment_order_key_valid(self, conn):
        """Non-null order_key in fact_payment must point to an existing fact_order row."""
        orphans = conn.execute(
            "SELECT COUNT(*) FROM fact_payment "
            "WHERE order_key IS NOT NULL "
            "  AND order_key NOT IN (SELECT order_key FROM fact_order)"
        ).fetchone()[0]
        assert orphans == 0, (
            f"{orphans} fact_payment rows have a non-null order_key with no fact_order parent"
        )

    def test_fact_customer_issue_customer_key_valid(self, conn):
        """Non-null customer_key in fact_customer_issue must point to an existing dim_customer row."""
        orphans = conn.execute(
            "SELECT COUNT(*) FROM fact_customer_issue "
            "WHERE customer_key IS NOT NULL "
            "  AND customer_key NOT IN (SELECT customer_key FROM dim_customer)"
        ).fetchone()[0]
        assert orphans == 0, (
            f"{orphans} fact_customer_issue rows have a dangling non-null customer_key"
        )

    def test_exactly_one_null_customer_key_in_fact_order(self, conn):
        """Exactly one order (O1019 → C999) must have a NULL customer_key."""
        null_count = conn.execute(
            "SELECT COUNT(*) FROM fact_order WHERE customer_key IS NULL"
        ).fetchone()[0]
        assert null_count == 1, (
            f"Expected 1 null customer_key in fact_order (O1019 → C999), got {null_count}"
        )

    def test_exactly_one_null_product_key_in_fact_order(self, conn):
        """Exactly one order (O1020 → P999) must have a NULL product_key."""
        null_count = conn.execute(
            "SELECT COUNT(*) FROM fact_order WHERE product_key IS NULL"
        ).fetchone()[0]
        assert null_count == 1, (
            f"Expected 1 null product_key in fact_order (O1020 → P999), got {null_count}"
        )

    def test_exactly_one_null_order_key_in_fact_payment(self, conn):
        """Exactly one payment (PMT029 → O9999) must be an orphan with a NULL order_key."""
        null_count = conn.execute(
            "SELECT COUNT(*) FROM fact_payment WHERE order_key IS NULL"
        ).fetchone()[0]
        assert null_count == 1, (
            f"Expected 1 null order_key in fact_payment (PMT029 → O9999), got {null_count}"
        )

    def test_exactly_one_null_customer_key_in_fact_customer_issue(self, conn):
        """Exactly one ticket (T005 → C999) must have a NULL customer_key."""
        null_count = conn.execute(
            "SELECT COUNT(*) FROM fact_customer_issue WHERE customer_key IS NULL"
        ).fetchone()[0]
        assert null_count == 1, (
            f"Expected 1 null customer_key in fact_customer_issue (T005 → C999), got {null_count}"
        )


# ---------------------------------------------------------------------------
# 3. Amount checks
# ---------------------------------------------------------------------------

class TestAmountChecks:
    """
    Validate domain-logic boundaries: aggregated amounts must be positive where
    expected, and known anomalies (negative quantity, payment mismatches) must
    appear exactly as many times as the source data warrants.
    """

    def test_completed_revenue_is_positive(self, conn):
        """Aggregate gross revenue for completed orders must be a positive number."""
        total = conn.execute(
            "SELECT COALESCE(SUM(gross_order_amount), 0) FROM fact_order "
            "WHERE LOWER(order_status) = 'completed'"
        ).fetchone()[0]
        assert total > 0, f"Total completed revenue is non-positive: {total}"

    def test_active_product_unit_prices_positive(self, conn):
        """Every active dim_product row must have a positive unit_price after the TEXT cast."""
        bad = conn.execute(
            "SELECT COUNT(*) FROM dim_product "
            "WHERE active_flag = 1 AND (unit_price IS NULL OR unit_price <= 0)"
        ).fetchone()[0]
        assert bad == 0, f"{bad} active dim_product rows have a non-positive unit_price"

    def test_exactly_one_negative_quantity_completed_order(self, conn):
        """
        Exactly one completed order (O1030, quantity = -1) must have a non-positive quantity.
        This is the known DQ007 violation; any additional occurrences indicate a regression.
        """
        neg_qty = conn.execute(
            "SELECT COUNT(*) FROM fact_order "
            "WHERE LOWER(order_status) = 'completed' AND quantity <= 0"
        ).fetchone()[0]
        assert neg_qty == 1, (
            f"Expected 1 negative-qty completed order (O1030), got {neg_qty}"
        )

    def test_exactly_one_order_amount_mismatch(self, conn):
        """
        Exactly one order (O1021, stated 50.00 vs computed 44.00) must have an
        order_amount_variance with ABS > 0.01.  This is the DQ008 violation.
        """
        mismatch = conn.execute(
            "SELECT COUNT(*) FROM fact_order "
            "WHERE order_amount_variance IS NOT NULL "
            "  AND ABS(order_amount_variance) > 0.01"
        ).fetchone()[0]
        assert mismatch == 1, (
            f"Expected 1 order amount mismatch (O1021), got {mismatch}"
        )

    def test_exactly_one_settled_payment_amount_mismatch(self, conn):
        """
        Exactly one settled payment (PMT021 / O1021) must differ from its completed
        order's gross total by more than 0.01 — the DQ010 violation.
        Non-settled statuses (voided, refunded) are intentionally excluded.
        """
        mismatch = conn.execute(
            "SELECT COUNT(*) FROM fact_payment fp "
            "JOIN fact_order fo ON fp.order_key = fo.order_key "
            "WHERE LOWER(fp.payment_status) = 'settled' "
            "  AND LOWER(fo.order_status) = 'completed' "
            "  AND ABS(fp.payment_amount - fo.gross_order_amount) > 0.01"
        ).fetchone()[0]
        assert mismatch == 1, (
            f"Expected 1 settled-payment amount mismatch (PMT021/O1021), got {mismatch}"
        )


# ---------------------------------------------------------------------------
# 4. Parsing checks
# ---------------------------------------------------------------------------

class TestParsingChecks:
    """
    Verify primary-key completeness, schema conformance, and that type-casting
    from TEXT staging succeeded for all expected rows.
    """

    def test_dim_customer_pk_not_null(self, conn):
        """customer_key must be non-null for every dim_customer row."""
        nulls = conn.execute(
            "SELECT COUNT(*) FROM dim_customer WHERE customer_key IS NULL"
        ).fetchone()[0]
        assert nulls == 0, f"{nulls} dim_customer rows have a NULL customer_key"

    def test_dim_product_pk_not_null(self, conn):
        """product_key must be non-null for every dim_product row."""
        nulls = conn.execute(
            "SELECT COUNT(*) FROM dim_product WHERE product_key IS NULL"
        ).fetchone()[0]
        assert nulls == 0, f"{nulls} dim_product rows have a NULL product_key"

    def test_fact_order_pk_not_null(self, conn):
        """order_key must be non-null for every fact_order row."""
        nulls = conn.execute(
            "SELECT COUNT(*) FROM fact_order WHERE order_key IS NULL"
        ).fetchone()[0]
        assert nulls == 0, f"{nulls} fact_order rows have a NULL order_key"

    def test_fact_payment_pk_not_null(self, conn):
        """payment_key must be non-null for every fact_payment row."""
        nulls = conn.execute(
            "SELECT COUNT(*) FROM fact_payment WHERE payment_key IS NULL"
        ).fetchone()[0]
        assert nulls == 0, f"{nulls} fact_payment rows have a NULL payment_key"

    def test_fact_customer_issue_pk_not_null(self, conn):
        """ticket_id must be non-null for every fact_customer_issue row."""
        nulls = conn.execute(
            "SELECT COUNT(*) FROM fact_customer_issue WHERE ticket_id IS NULL"
        ).fetchone()[0]
        assert nulls == 0, f"{nulls} fact_customer_issue rows have a NULL ticket_id"

    def test_all_order_dates_parseable(self, conn):
        """
        All 30 fact_order rows must have a non-null order_date.
        The mixed-format parser (transform.parse_timestamp) must handle every input
        format in orders.csv; a NULL here means a format was silently rejected.
        """
        total = conn.execute("SELECT COUNT(*) FROM fact_order").fetchone()[0]
        non_null = conn.execute(
            "SELECT COUNT(*) FROM fact_order WHERE order_date IS NOT NULL"
        ).fetchone()[0]
        assert non_null == total, (
            f"{total - non_null} fact_order rows have an unparseable order_date"
        )

    def test_exactly_one_ticket_timestamp_unparseable(self, conn):
        """
        Exactly one ticket (T010, created_ts = 'bad_timestamp') must have a NULL
        created_date — the DQ011 violation.  All other tickets must parse successfully.
        """
        null_dates = conn.execute(
            "SELECT COUNT(*) FROM fact_customer_issue WHERE created_date IS NULL"
        ).fetchone()[0]
        assert null_dates == 1, (
            f"Expected 1 NULL created_date in fact_customer_issue (T010), got {null_dates}"
        )

    def test_unit_price_cast_to_numeric(self, conn):
        """All dim_product.unit_price values must be non-null REAL after casting from TEXT staging."""
        non_numeric = conn.execute(
            "SELECT COUNT(*) FROM dim_product WHERE unit_price IS NULL"
        ).fetchone()[0]
        assert non_numeric == 0, (
            f"{non_numeric} dim_product rows still have NULL unit_price after REAL cast"
        )

    def test_country_normalized_to_usa(self, conn):
        """
        All dim_customer rows with a non-null standard_country must have 'USA'.
        Raw variants ('US', 'United States') must have been collapsed by normalize_country().
        """
        non_standard = conn.execute(
            "SELECT COUNT(*) FROM dim_customer "
            "WHERE standard_country IS NOT NULL AND standard_country != 'USA'"
        ).fetchone()[0]
        assert non_standard == 0, (
            f"{non_standard} dim_customer rows have a non-standard country value"
        )

    def test_state_codes_are_two_letters(self, conn):
        """
        All non-null standard_state values in dim_customer must be two-letter codes.
        Full state names ('Illinois', 'New York', …) must have been mapped by normalize_state().
        """
        bad = conn.execute(
            "SELECT COUNT(*) FROM dim_customer "
            "WHERE standard_state IS NOT NULL AND LENGTH(standard_state) != 2"
        ).fetchone()[0]
        assert bad == 0, (
            f"{bad} dim_customer rows have a standard_state that is not a two-letter code"
        )
