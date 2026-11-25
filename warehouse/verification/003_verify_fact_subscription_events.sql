
-- ============================================================
-- File: 003_verify_fact_subscription_events.sql
-- Purpose: Verify mart.fact_subscription_events
-- ============================================================

-- 1. Verify columns and data types.
SELECT
    column_name,
    data_type,
    is_nullable,
    column_default
FROM information_schema.columns
WHERE table_schema = 'mart'
  AND table_name = 'fact_subscription_events'
ORDER BY ordinal_position;


-- 2. Verify constraints.
SELECT
    conname AS constraint_name,
    contype AS constraint_type,
    pg_get_constraintdef(oid) AS definition
FROM pg_constraint
WHERE conrelid = 'mart.fact_subscription_events'::regclass
ORDER BY conname;


-- 3. Verify indexes.
SELECT
    indexname,
    indexdef
FROM pg_indexes
WHERE schemaname = 'mart'
  AND tablename = 'fact_subscription_events'
ORDER BY indexname;


-- 4. Check duplicate event IDs.
SELECT
    event_id,
    COUNT(*) AS event_count
FROM mart.fact_subscription_events
GROUP BY event_id
HAVING COUNT(*) > 1;


-- 5. Check events with invalid customer dimension references.
SELECT
    f.event_id,
    f.customer_sk
FROM mart.fact_subscription_events f
LEFT JOIN mart.dim_customer d
    ON f.customer_sk = d.customer_sk
WHERE d.customer_sk IS NULL;
