
-- =====================================================
-- Multi-Source Data Pipeline
-- Target Warehouse: Supabase PostgreSQL
-- Purpose: Raw data landing schemas
-- =====================================================

-- E-commerce source data
CREATE SCHEMA IF NOT EXISTS raw_ecom;

-- SaaS source data
CREATE SCHEMA IF NOT EXISTS raw_saas;

-- =====================================================
-- Schema descriptions
-- =====================================================

COMMENT ON SCHEMA raw_ecom IS
'Raw landing area for data extracted from the E-commerce source database.';

COMMENT ON SCHEMA raw_saas IS
'Raw landing area for data extracted from the SaaS source database.';

-- =====================================================
-- End of initial schema setup
-- =====================================================
