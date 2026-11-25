
-- ============================================================
-- Verify: mart.dim_customer
-- Purpose: Inspect columns, constraints and indexes.
-- ============================================================

-- 1. Verify columns and data types.
SELECT
    column_name,
    data_type,
    is_nullable,
    column_default
FROM information_schema.columns
WHERE table_schema = 'mart'
  AND table_name = 'dim_customer'
ORDER BY ordinal_position;


-- 2. Verify constraints.
SELECT
    conname AS constraint_name,
    contype AS constraint_type,
    pg_get_constraintdef(oid) AS definition
FROM pg_constraint
WHERE conrelid = 'mart.dim_customer'::regclass
ORDER BY conname;


-- 3. Verify indexes.
SELECT
    indexname,
    indexdef
FROM pg_indexes
WHERE schemaname = 'mart'
  AND tablename = 'dim_customer'
ORDER BY indexname;


-- 4. Check that each source identity has at most one current record.
SELECT
    source_system,
    source_customer_id,
    COUNT(*) AS current_record_count
FROM mart.dim_customer
WHERE is_current = TRUE
GROUP BY
    source_system,
    source_customer_id
HAVING COUNT(*) > 1;


-- 5. Check for overlapping validity periods.
SELECT
    a.source_system,
    a.source_customer_id,
    a.customer_sk AS version_1,
    b.customer_sk AS version_2,
    a.valid_from AS version_1_start,
    a.valid_to AS version_1_end,
    b.valid_from AS version_2_start,
    b.valid_to AS version_2_end
FROM mart.dim_customer a
JOIN mart.dim_customer b
    ON a.source_system = b.source_system
   AND a.source_customer_id = b.source_customer_id
   AND a.customer_sk < b.customer_sk
   AND a.valid_from < COALESCE(
       b.valid_to,
       'infinity'::timestamptz
   )
   AND b.valid_from < COALESCE(
       a.valid_to,
       'infinity'::timestamptz
   );