# AI Usage

## Tooling & Setup
*   **Primary AI Assistant:** Claude Code (Sonnet 4.6 & Opus 4.7)
*   **Context Provided to AI:** Claude.md

---

## Task Log

### Task 1: Generating the basic strucutre of the repo (Used the strucutre provided in the document)

#### 1. Prompt
*   Build the folder structed based on the following structure: <Struture from document>

#### 2. Iterations
*   **Iteration 1:** Updated from DuckDB to SQLite {Personal preference} 

#### 3. Generated Code: Accepted vs. Rejected
*   **Accepted:** 
    *   Generated a the desired structure
*   **Rejected:** 
    *   N/A

#### 4. Manual Fixes & Modifications
*   N/A

#### 5. Verification & Testing Steps
*   Opened and checked all the files and folders

---

### Task 2: Generating Claude.md

#### 1. Prompt
*   /init

#### 2. Iterations
*   **Iteration 1:** Updated from DuckDB to SQLite {Personal preference}
*   **Iteration 2:** Make sure the following hard constriants are present in the claude.md {Pulled by manually checking assesment doc} 

#### 3. Generated Code: Accepted vs. Rejected
*   **Accepted:** 
    *   Generated after asking explicit changes to the MD file
*   **Rejected:** 
    *   N/A

#### 4. Manual Fixes & Modifications
*   Additional changes requested in further iteration like - switching to sqlite and adding more hard contraints

#### 5. Verification & Testing Steps
*   Opened and checked all the CLAUDE.md file

---

### Task 2: Planning (Used /ultraplan with Opus 4.7 xHigh effort)

#### 1. Prompt
*   /ultraplan Inspect every file in input_data/ read-only. For each: row count, columns, null rates, and a list of concrete data-quality
  issues you can find (duplicates, invalid references, malformed timestamps, negative/suspicious quantities, inactive products, payment
  mismatches, orphan records). Then read sttm_target_mapping.csv and data_quality_rules.csv and propose an implementation plan that
  derives the curated schema and DQ checks from those files. Do not write pipeline code yet. Output the plan as PLAN.md. 

#### 2. Iterations
*   **Iteration 1:** Add the plan.md manually to the project {As the ultraplan cloud session was not able to commit the file}

#### 3. Generated Code: Accepted vs. Rejected
*   **Accepted:** 
    *   Accepted the Plan generated in the PLAN.md
*   **Rejected:** 
    *   Decided to reject the following issue "Inactive product sold: P011 (Protein Bar Box) has active_flag=N but is referenced by completed order O1015."

#### 4. Manual Fixes & Modifications
*   For Customer tables reconciliation, manually chose deduplicate based on same IDs and same full name + Phone/email
*   When agent asked to weather to use pandas or SQL, chose sql since working with a small dataset
*   Decided to reject the following issue "Inactive product sold: P011 (Protein Bar Box) has active_flag=N but is referenced by completed order O1015." - since the product could have been made inactive after the order happened

#### 5. Verification & Testing Steps
*   Verified customer dataset. Decided to merge C001 and C019 since both have same name, same number but the email-id and signup date is different, indicaiting that it is a duplication. Also there were no orders from C019

---

### Task 2: Generating the ingest.py script

#### 1. Prompt
*   Read each CSV with stdlib csv.DictReader; read JSONL line-by-line with json.loads. Create staging_customers, staging_products, staging_orders, staging_payments, staging_support_tickets in outputs/curated.sqlite with every column TEXT (satisfies the TEXT-staging constraint). Load as-is, no cleaning.

#### 2. Iterations
*   **Iteration 1:**  Add comments above each method and also in places which might be hard to understand.
*   **Iteration 2:**  Add logging to the script.

#### 3. Generated Code: Accepted vs. Rejected
*   **Accepted:** 
    *   Accepted the Plan generated in the PLAN.md
*   **Rejected:** 
    *   N/A

#### 4. Manual Fixes & Modifications
*   N/A

#### 5. Verification & Testing Steps
*   Verified the staged tables and cross checked it with the CSV. Made sure no data got dropped.

---