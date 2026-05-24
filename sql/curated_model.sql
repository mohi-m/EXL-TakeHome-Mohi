-- curated_model.sql
-- Companion DDL and transformation SQL mirroring src/transform.py.
-- Assumes staging tables already exist (run src/ingest.py first).
--

-- ============================================================
-- DROP AND RECREATE ALL CURATED TABLES
-- ============================================================

DROP TABLE IF EXISTS id_crosswalk;
DROP TABLE IF EXISTS dim_customer;
DROP TABLE IF EXISTS dim_product;
DROP TABLE IF EXISTS fact_order;
DROP TABLE IF EXISTS fact_payment;
DROP TABLE IF EXISTS fact_customer_issue;
DROP TABLE IF EXISTS dq_exception_report;

-- Tracks non-canonical customer IDs merged during deduplication.
-- Populated by Python's union-find (cross-ID) and by the exact-id pass below.
CREATE TABLE id_crosswalk (
    old_customer_id       TEXT PRIMARY KEY,
    canonical_customer_id TEXT NOT NULL
);

-- One row per canonical customer after two-pass deduplication.
CREATE TABLE dim_customer (
    customer_key             TEXT PRIMARY KEY,
    full_name                TEXT,
    email                    TEXT,
    phone                    TEXT,
    standard_country         TEXT,
    standard_state           TEXT,
    signup_date              TEXT,
    loyalty_tier             TEXT,
    duplicate_resolution_flag INTEGER
);

-- Product reference dimension; unit_price and active_flag are typed for arithmetic.
CREATE TABLE dim_product (
    product_key  TEXT PRIMARY KEY,
    product_name TEXT,
    category     TEXT,
    unit_price   REAL,
    active_flag  INTEGER
);

-- One row per unique order_id; computed variance columns support DQ008.
CREATE TABLE fact_order (
    order_key               TEXT PRIMARY KEY,
    customer_key            TEXT,
    product_key             TEXT,
    order_date              TEXT,
    quantity                INTEGER,
    order_status            TEXT,
    shipping_state          TEXT,
    gross_order_amount      REAL,
    calculated_order_amount REAL,
    order_amount_variance   REAL
);

-- One row per payment; order_key is NULL for orphan payments (DQ009).
CREATE TABLE fact_payment (
    payment_key    TEXT PRIMARY KEY,
    order_key      TEXT,
    payment_date   TEXT,
    payment_method TEXT,
    payment_status TEXT,
    payment_amount REAL
);

-- Support tickets with resolved customer FK and parsed timestamp.
CREATE TABLE fact_customer_issue (
    ticket_id      TEXT PRIMARY KEY,
    customer_key   TEXT,
    created_date   TEXT,
    channel        TEXT,
    issue_category TEXT,
    sentiment      TEXT,
    description    TEXT
);

-- Accumulates one row per failing record per DQ rule; no PK by design.
CREATE TABLE dq_exception_report (
    rule_id           TEXT,
    dataset           TEXT,
    record_key        TEXT,
    severity          TEXT,
    issue_description TEXT,
    suggested_action  TEXT
);