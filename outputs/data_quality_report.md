# Data Quality Report

**Generated:** 2026-05-23  
**Rules source:** `input_data/data_quality_rules.csv`

---

## Summary

**21 exception(s)** detected across **14 rules** (14 triggered, 0 passed clean).

| Rule ID | Dataset | Severity | Description | Exceptions |
|---------|---------|----------|-------------|:----------:|
| DQ001 | customers | High | exact duplicate customer_ids exist in source data | 1 |
| DQ002 | customers | Medium | email is missing or absent for a customer | 1 |
| DQ003 | customers | Medium | country or state value is non-standard (full name or variant spelling) | 8 |
| DQ004 | orders | High | exact duplicate order_ids exist in source data | 1 |
| DQ005 | orders | High | order references a customer_id not present in the customers dataset | 1 |
| DQ006 | orders | High | order references a product_id not present in the products dataset | 1 |
| DQ007 | orders | High | completed order has a non-positive quantity | 1 |
| DQ008 | orders | High | stated order_total does not match quantity x unit_price | 1 |
| DQ009 | payments | High | payment references an order_id not present in the orders dataset | 1 |
| DQ010 | payments | High | settled payment amount differs from the completed order total | 1 |
| DQ011 | support_tickets | Medium | ticket created_ts cannot be parsed to a valid timestamp | 1 |
| DQ012 | support_tickets | Medium | ticket references a customer_id not present in the customers dataset | 1 |
| DQ013 | customers | High | different customer_ids resolve to the same person via name and contact-info matching | 1 |
| DQ014 | orders | Medium | order references a product with active_flag = 0 (discontinued product) | 1 |

---

## Rule Details

### DQ001 — exact duplicate customer_ids exist in source data
**Dataset:** customers | **Severity:** High | **Status:** 1 exception(s)

| Record Key | Issue Description |
|------------|-------------------|
| `C006` | customer_id C006 appears 2 times in source (exact duplicate rows) |

**Suggested action:** No further action needed

---

### DQ002 — email is missing or absent for a customer
**Dataset:** customers | **Severity:** Medium | **Status:** 1 exception(s)

| Record Key | Issue Description |
|------------|-------------------|
| `C004` | Customer C004 has no email address on record |

**Suggested action:** Contact the customer to obtain a valid email address and update the source record; flag account for manual outreach

---

### DQ003 — country or state value is non-standard (full name or variant spelling)
**Dataset:** customers | **Severity:** Medium | **Status:** 8 exception(s)

| Record Key | Issue Description |
|------------|-------------------|
| `C002` | Customer C002 country 'US' is a non-standard variant; should be 'USA' |
| `C002` | Customer C002 state 'Illinois' is a full name; should use two-letter code |
| `C003` | Customer C003 country 'United States' is a non-standard variant; should be 'USA' |
| `C006` | Customer C006 country 'US' is a non-standard variant; should be 'USA' |
| `C006` | Customer C006 state 'New York' is a full name; should use two-letter code |
| `C008` | Customer C008 state 'Texas' is a full name; should use two-letter code |
| `C011` | Customer C011 country 'United States' is a non-standard variant; should be 'USA' |
| `C015` | Customer C015 state 'Florida' is a full name; should use two-letter code |

**Suggested action:** No further action needed

---

### DQ004 — exact duplicate order_ids exist in source data
**Dataset:** orders | **Severity:** High | **Status:** 1 exception(s)

| Record Key | Issue Description |
|------------|-------------------|
| `O1018` | order_id O1018 appears 2 times in source (exact duplicate rows) |

**Suggested action:** No further action needed

---

### DQ005 — order references a customer_id not present in the customers dataset
**Dataset:** orders | **Severity:** High | **Status:** 1 exception(s)

| Record Key | Issue Description |
|------------|-------------------|
| `O1019` | Order O1019 references non-existent customer_id 'C999' |

**Suggested action:** Verify and correct the customer_id on the order; quarantine the order for manual review if the customer cannot be found

---

### DQ006 — order references a product_id not present in the products dataset
**Dataset:** orders | **Severity:** High | **Status:** 1 exception(s)

| Record Key | Issue Description |
|------------|-------------------|
| `O1020` | Order O1020 references non-existent product_id 'P999' |

**Suggested action:** Verify and correct the product_id on the order; mark for review if the product cannot be identified

---

### DQ007 — completed order has a non-positive quantity
**Dataset:** orders | **Severity:** High | **Status:** 1 exception(s)

| Record Key | Issue Description |
|------------|-------------------|
| `O1030` | Completed order O1030 has non-positive quantity -1 (gross total: -21.0) |

**Suggested action:** Investigate for data-entry error; correct the quantity or reclassify the order status (e.g. returned or cancelled)

---

### DQ008 — stated order_total does not match quantity x unit_price
**Dataset:** orders | **Severity:** High | **Status:** 1 exception(s)

| Record Key | Issue Description |
|------------|-------------------|
| `O1021` | Order O1021 stated total 50.0 does not match computed 44.0 (variance: 6.0) |

**Suggested action:** Reconcile the order total with line-item pricing; escalate discrepancy to finance for adjustment or repricing

---

### DQ009 — payment references an order_id not present in the orders dataset
**Dataset:** payments | **Severity:** High | **Status:** 1 exception(s)

| Record Key | Issue Description |
|------------|-------------------|
| `PMT029` | Payment PMT029 references non-existent order_id 'O9999' |

**Suggested action:** Trace the orphan payment to its correct order; link or initiate a finance write-off if unresolvable

---

### DQ010 — settled payment amount differs from the completed order total
**Dataset:** payments | **Severity:** High | **Status:** 1 exception(s)

| Record Key | Issue Description |
|------------|-------------------|
| `PMT021` | Payment PMT021 settled amount 44.0 does not match completed order O1021 total 50.0 |

**Suggested action:** Reconcile the settled amount with the order total; initiate a payment adjustment or chargeback as appropriate

---

### DQ011 — ticket created_ts cannot be parsed to a valid timestamp
**Dataset:** support_tickets | **Severity:** Medium | **Status:** 1 exception(s)

| Record Key | Issue Description |
|------------|-------------------|
| `T010` | Ticket T010 has unparseable created_ts: 'bad_timestamp' |

**Suggested action:** Correct the malformed timestamp in the source system; enforce ISO 8601 format (YYYY-MM-DD HH:MM:SS) at ticket creation

---

### DQ012 — ticket references a customer_id not present in the customers dataset
**Dataset:** support_tickets | **Severity:** Medium | **Status:** 1 exception(s)

| Record Key | Issue Description |
|------------|-------------------|
| `T005` | Ticket T005 references non-existent customer_id 'C999' |

**Suggested action:** Verify the customer reference on the ticket; link to the correct customer or create a new customer record

---

### DQ013 — different customer_ids resolve to the same person via name and contact-info matching
**Dataset:** customers | **Severity:** High | **Status:** 1 exception(s)

| Record Key | Issue Description |
|------------|-------------------|
| `C019` | customer_id C019 resolves to the same person as canonical customer C001 (matching full_name + phone or email) |

**Suggested action:** Verify the diplicates via the id_crosswalk table; currently it has been updated using the most complete or if both complete, the lowest customer_key

---

### DQ014 — order references a product with active_flag = 0 (discontinued product)
**Dataset:** orders | **Severity:** Medium | **Status:** 1 exception(s)

| Record Key | Issue Description |
|------------|-------------------|
| `O1015` | Order O1015 references inactive product P011 (active_flag = 0) |

**Suggested action:** Remove the inactive product from the order or reactivate the product; verify fulfilment capability and review pricing before shipment

---
