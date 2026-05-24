# Business Answers

**Generated:** 2026-05-23  
**Source database:** `outputs/curated.sqlite`

---

## Q1: What is completed revenue by month?

| month   | completed_revenue |
| ------- | ----------------- |
| 2025-03 | 440.7             |
| 2025-04 | 394.95            |
| 2025-05 | 425.2             |

---

## Q2: Who are the top 10 customers by completed order value?

| customer_key | full_name         | total_completed_value |
| ------------ | ----------------- | --------------------- |
| C010         | Lucas Taylor      | 194.98                |
| C012         | James Thomas      | 133.98                |
| C016         | Henry Martin      | 133.98                |
| C007         | Sophia Miller     | 99.98                 |
| C002         | Liam Nguyen       | 89.99                 |
| C009         | Isabella Moore    | 83.25                 |
| C004         | Emma Brown        | 74.97                 |
| C003         | Noah Williams     | 73.75                 |
| C013         | Charlotte Jackson | 59.0                  |
| C018         | Daniel Clark      | 54.0                  |

---

## Q3: Which orders have payment mismatches, missing payments, invalid customer references, invalid product references, or suspicious quantities?

| order_key | order_status | gross_order_amount | invalid_customer | invalid_product | suspicious_qty | total_mismatch | missing_payment | payment_mismatch |
| --------- | ------------ | ------------------ | ---------------- | --------------- | -------------- | -------------- | --------------- | ---------------- |
| O1019     | completed    | 24.99              | Yes              | No              | No             | No             | No              | No               |
| O1020     | completed    | 12.99              | No               | Yes             | No             | No             | No              | No               |
| O1021     | completed    | 50.0               | No               | No              | No             | Yes            | No              | Yes              |
| O1024     | completed    | 42.0               | No               | No              | No             | No             | Yes             | No               |
| O1030     | completed    | -21.0              | No               | No              | Yes            | No             | No              | No               |

---

## Q4: Which states have the highest completed revenue?

| shipping_state | completed_revenue |
| -------------- | ----------------- |
| IL             | 315.95            |
| MA             | 278.23            |
| WA             | 192.98            |
| CA             | 169.72            |
| TX             | 141.98            |
| NY             | 96.0              |
| FL             | 65.99             |

---

## Q5: Is there any visible relationship between negative support tickets and order/payment exceptions?

| ticket_id | customer_key | customer_name  | issue_category | orders_placed | orders_with_total_mismatch | orders_missing_payment | orders_with_payment_mismatch | orders_with_suspicious_qty |
| --------- | ------------ | -------------- | -------------- | ------------- | -------------------------- | ---------------------- | ---------------------------- | -------------------------- |
| T007      | C002         | Liam Nguyen    | billing        | 2             | 1                          | 0                      | 1                            | 0                          |
| T009      | C018         | Daniel Clark   | billing        | 2             | 0                          | 0                      | 0                            | 1                          |
| T001      | C001         | Ava Patel      | delivery       | 2             | 0                          | 0                      | 0                            | 0                          |
| T003      | C014         | Benjamin White | return         | 2             | 0                          | 0                      | 0                            | 0                          |
| T004      | C006         | Mason Davis    | billing        | 1             | 0                          | 0                      | 0                            | 0                          |
| T005      | NULL         | Unknown        | account        | 0             | 0                          | 0                      | 0                            | 0                          |
| T010      | C017         | Harper Lee     | delivery       | 1             | 0                          | 0                      | 0                            | 0                          |

---
