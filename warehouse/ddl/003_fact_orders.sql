
-- ============================================================
-- File: 003_fact_orders.sql
-- Purpose: Create the e-commerce order fact table.
-- Schema: mart
--
-- Grain:
-- One row per unique e-commerce order, identified by order_id.
-- ============================================================

CREATE TABLE IF NOT EXISTS mart.fact_orders (

    -- Source-system order identifier.
    order_id BIGINT,

    -- Foreign key to the applicable SCD Type II customer version.
    customer_sk BIGINT NOT NULL,

    -- Order details.
    created_at TIMESTAMPTZ NOT NULL,
    status TEXT NOT NULL,
    payment_status TEXT NOT NULL,

    -- Order-level financial measures.
    subtotal NUMERIC NOT NULL,
    discount NUMERIC NOT NULL,
    tax NUMERIC NOT NULL,
    shipping_fee NUMERIC NOT NULL,
    total NUMERIC NOT NULL,

    -- Fact-table primary key.
    CONSTRAINT pk_fact_orders
        PRIMARY KEY (order_id),

    -- Link each order to its customer dimension version.
    CONSTRAINT fk_fact_orders_customer
        FOREIGN KEY (customer_sk)
        REFERENCES mart.dim_customer (customer_sk)
);

-- Support customer-level order analysis.
CREATE INDEX IF NOT EXISTS idx_fact_orders_customer
ON mart.fact_orders (customer_sk);

-- Support date-based order analysis.
CREATE INDEX IF NOT EXISTS idx_fact_orders_created_at
ON mart.fact_orders (created_at);

-- Document the table grain.
COMMENT ON TABLE mart.fact_orders IS
'Grain: One row per unique e-commerce order, identified by order_id.';
