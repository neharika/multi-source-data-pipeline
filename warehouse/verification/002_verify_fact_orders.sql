SELECT
    column_name,
    data_type,
    is_nullable,
    column_default
FROM information_schema.columns
WHERE table_schema = 'mart'
  AND table_name = 'fact_orders'
ORDER BY ordinal_position;


-- check constraints
SELECT
    conname AS constraint_name,
    contype AS constraint_type,
    pg_get_constraintdef(oid) AS definition
FROM pg_constraint
WHERE conrelid = 'mart.fact_orders'::regclass
ORDER BY conname;

--check indexes
SELECT
    indexname,
    indexdef
FROM pg_indexes
WHERE schemaname = 'mart'
  AND tablename = 'fact_orders'
ORDER BY indexname;

-- 4. Check duplicate order IDs.
SELECT
    order_id,
    COUNT(*) AS order_count
FROM mart.fact_orders
GROUP BY order_id
HAVING COUNT(*) > 1;

-- 5. Check orders with invalid customer dimension references.
SELECT
    f.order_id,
    f.customer_sk
FROM mart.fact_orders f
LEFT JOIN mart.dim_customer d
    ON f.customer_sk = d.customer_sk
WHERE d.customer_sk IS NULL;