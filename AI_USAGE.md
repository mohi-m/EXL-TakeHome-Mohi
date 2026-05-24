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

### Task 3: Planning (Used /ultraplan with Opus 4.7 xHigh effort)

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

### Task 4: Generating the ingest.py script

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

### Task 5: Generating the transform.py script

#### 1. Prompt
*   src/transform.py — derive curated tables from sttm_target_mapping.csv
Parse sttm_target_mapping.csv to build the target-table column lists, so the curated DDL/columns come from the mapping, not literals.
Shared helpers: parse_timestamp() (tries %Y-%m-%d %H:%M:%S, %Y-%m-%dT%H:%M:%SZ, %m/%d/%Y %H:%M, %Y/%m/%d %H:%M, %m-%d-%Y %H:%M, date-only variants; returns None on failure); STATE_MAP (Illinois→IL, New York→NY, Texas→TX, Florida→FL, …); normalize_country() (USA/US/United States→USA); to_decimal().
dim_customer: dedup in two passes — (a) collapse exact duplicate customer_id keeping the most-complete row; (b) group rows with equal normalized full_name AND matching phone or email, pick lowest customer_id as customer_key, emit an id_crosswalk (old_id→canonical). Build full_name, lowercased email (NULL flagged not fabricated), standard_country, standard_state, preserved loyalty_tier.
dim_product: preserve id/name/category, cast unit_price decimal. Keep active_flag available for the inactive-product check.
fact_order: dedup order_id; remap customer_key through the crosswalk; validate customer/product FKs (failures → exception report, row still kept with NULL key per "no silent drops"); order_date via parse_timestamp; quantity int; gross_order_amount decimal plus computed quantity*unit_price for the DQ008 comparison.
fact_payment: preserve payment_id; FK order_key to fact_order (orphans → exception report); payment_amount decimal.
fact_customer_issue: customer_key via crosswalk (FK where possible), preserve issue_category, sentiment; parse created_ts (failures flagged).

#### 2. Iterations
*   **Iteration 1:**  Update the @input_data/sttm_target_mapping.csv and use the following columns in it: {Target model copied from the assesment doc}
*   **Iteration 2:**  The transform script does not need to run the injest script as all of this will be running through a parent pipeline script. Also the ingest and transform script should not be dropping tables by default, there should be a flag which decides weather to drop and reconstruct or upsert.
*   **Iteration 3:**  Add the DDL statement from the @src/transform.py script to the @sql/curated_model.sql file

#### 3. Generated Code: Accepted vs. Rejected
*   **Accepted:** 
    *   
*   **Rejected:** 
    *   Initial prompt's output rejected since the sttm_taget_mapping csv was missing a lot of columns that was required in the assement doc.
    *   The generated transform script was also running the ingest script which was not intended, hence rejected the version.
    *   REJCTED COMPLETELY as it started deviating away from the plan


#### 4. Manual Fixes & Modifications
*   N/A

#### 5. Verification & Testing Steps
*   Verified the Schema of each table created with the sttm_target_mapping also verifed the values in the table especially the errneous cases.
*   Verfied the updated sttm file using git diff

---

### Task 5: Generating the transform.py script {RETRY}

#### 1. Prompt
*   Read the @PLAN.md and perform step 2 in part B

#### 2. Iterations
*   **Iteration 1:**  N/A

#### 3. Generated Code: Accepted vs. Rejected
*   **Accepted:** 
    *   Asking claude code to read the plan.md kept it grounded to the plan and prduced the correct output.
*   **Rejected:** 
    *   N/A


#### 4. Manual Fixes & Modifications
*   N/A

#### 5. Verification & Testing Steps
*   Verified the Schema of each table created with the sttm_target_mapping also verifed the values in the table especially the errneous cases.

---

### Task 6: Generating the quality_checks.py script

#### 1. Prompt
*   Read the @PLAN.md and perform step 3 in part B

#### 2. Iterations
*   **Iteration 1:**  Perform the following changes:  
  - create a new row in the @input_data/data_quality_rules.csv for the cross=id duplicates record and then update the @src/quality_checks.py script accordingly                               
  - create a new row in the @input_data/data_quality_rules.csv for the inactive product sold rule                                                                                         
  - Also in the script, populate the suggested_action column. Add a suggest action for reach data quality issue in the script and I will manually check it.
  - Also update the @src/quality_checks.py script to output the data quality issues to the @outputs/exceptions.csv and also generate a report to @outputs/data_quality_report.md

#### 3. Generated Code: Accepted vs. Rejected
*   **Accepted:** 
    *   Accepted after the first iteration as it was able to indentify all the quality issues and some more.
*   **Rejected:** 
    *   N/A


#### 4. Manual Fixes & Modifications
*   Some of the suggested action did not make sense so updated it manually and made it blank. The issues like Country name US, USA and United States all normalised to USA does not need any further actions. So these changes are still recorded in the dq_exception_report but no suggested actions needed to be added for it.

#### 5. Verification & Testing Steps
*   Verfied each of the exception added in the dq_exception_record table and double checked if it missied any other issue or not.

---

### Task 7: Generating the reporting.py script {REJECTED}

#### 1. Prompt
*   Read the @PLAN.md and perform step 4 in part B

#### 2. Iterations
*   **Iteration 1:**  Dont hard code the values in the script

#### 3. Generated Code: Accepted vs. Rejected
*   **Accepted:** 
    *   N/A
*   **Rejected:** 
    *   It consistently hardcoded the ids and values in the script making this not extesible.


#### 4. Manual Fixes & Modifications
*   N/A

#### 5. Verification & Testing Steps
*   Verified the output generated for each question

---

### Task 7: Generating the reporting.py script {REJECTED}

#### 1. Prompt
*   Read the @PLAN.md and perform step 4 in part B

#### 2. Iterations
*   **Iteration 1:**  Update the fifth query in the @sql/business_questions.sql to only look for issues in the order/payment tables and not customer table.

#### 3. Generated Code: Accepted vs. Rejected
*   **Accepted:** 
    *   Accepted the changes as the output generated was correct and manually verfifed
*   **Rejected:** 
    *   N/A


#### 4. Manual Fixes & Modifications
*   N/A

#### 5. Verification & Testing Steps
*   Verified each query and the output generated by it.

---


### Task 8: Generating the pipeline.py script

#### 1. Prompt
*   Read the @PLAN.md and perform step 5 in part B

#### 2. Iterations
*   **Iteration 1:**  N/A

#### 3. Generated Code: Accepted vs. Rejected
*   **Accepted:** 
    *   Generated the code perfectly since it was a straight forward task.
*   **Rejected:** 
    *   N/A


#### 4. Manual Fixes & Modifications
*   N/A

#### 5. Verification & Testing Steps
*   Ran the pipeline script and verfied the output.

---

### Task 9: Generating the curated_model.sql file qhich contains the DDL statements

#### 1. Prompt
*   Read the @PLAN.md and perform step 5 in part B

#### 2. Iterations
*   **Iteration 1:**  N/A

#### 3. Generated Code: Accepted vs. Rejected
*   **Accepted:** 
    *   The generated SQL was correct and created the correct database model.
*   **Rejected:** 
    *   N/A


#### 4. Manual Fixes & Modifications
*   It also generated the entire SQL logic to populate the field which was in the transform python script. Since this part was not required, I manually removed it.

#### 5. Verification & Testing Steps
*   Ran the entire sql script to make sure it created the tables appropriately.

---


