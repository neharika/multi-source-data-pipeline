
-- ============================================================
-- File: 002_dim_customer.sql
-- Purpose: Create the shared customer dimension.
-- Schema: mart
-- Design: Slowly Changing Dimension Type II (SCD Type II)
--
-- Grain:
-- One row per source customer identity per version
-- of its tracked attributes.
-- ============================================================

CREATE TABLE IF NOT EXISTS mart.dim_customer (

    -- Warehouse-generated surrogate key.
    customer_sk BIGINT GENERATED ALWAYS AS IDENTITY,

    -- Identifies the originating source system.
    source_system VARCHAR(20) NOT NULL,

    -- Original customer_id (ecom) or account_id (saas).
    source_customer_id BIGINT NOT NULL,

    -- Standardized attributes across source systems.
    customer_name TEXT,
    email TEXT,
    country TEXT,
    city TEXT,

    -- SaaS-specific attributes.
    industry TEXT,
    employee_count INTEGER,
    account_type TEXT,

    -- E-commerce-specific attributes.
    lifecycle_stage TEXT,
    acquisition_channel TEXT,

    -- SCD Type II validity columns.
    valid_from TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    valid_to TIMESTAMPTZ,
    is_current BOOLEAN NOT NULL DEFAULT TRUE,

    -- Surrogate primary key.
    CONSTRAINT pk_dim_customer
        PRIMARY KEY (customer_sk),

    -- Restrict records to the two known source systems.
    CONSTRAINT chk_dim_customer_source_system
        CHECK (source_system IN ('ecom', 'saas')),

    -- Prevent invalid validity periods.
    CONSTRAINT chk_dim_customer_validity
        CHECK (valid_to IS NULL OR valid_to > valid_from),

    -- Current records must not have an expiration timestamp.
    CONSTRAINT chk_dim_customer_current_validity
        CHECK (
            (is_current = TRUE AND valid_to IS NULL)
            OR
            (is_current = FALSE AND valid_to IS NOT NULL)
        )
);

-- Ensure that each source identity has at most one current version.
CREATE UNIQUE INDEX IF NOT EXISTS
    uq_dim_customer_current_source
ON mart.dim_customer (source_system, source_customer_id)
WHERE is_current = TRUE;

-- Support historical dimension lookups by source identity and validity.
CREATE INDEX IF NOT EXISTS
    idx_dim_customer_history
ON mart.dim_customer (
    source_system,
    source_customer_id,
    valid_from,
    valid_to
);

-- Document the table grain in PostgreSQL metadata.
COMMENT ON TABLE mart.dim_customer IS
'Grain: One row per source customer identity per version of its tracked attributes. SCD Type II dimension.';

COMMENT ON COLUMN mart.dim_customer.customer_sk IS
'Warehouse-generated surrogate key identifying a specific dimension version.';

COMMENT ON COLUMN mart.dim_customer.source_customer_id IS
'Original customer_id from ecom or account_id from saas.';

COMMENT ON COLUMN mart.dim_customer.valid_from IS
'Inclusive timestamp from which this dimension version is valid.';

COMMENT ON COLUMN mart.dim_customer.valid_to IS
'Exclusive timestamp at which this dimension version expires. NULL indicates the current version.';

COMMENT ON COLUMN mart.dim_customer.is_current IS
'TRUE for the current dimension version; FALSE for historical versions.';



