
-- ============================================================
-- File: 001_create_mart_schema.sql
-- Purpose: Create the analytical serving schema.
-- Target: Supabase PostgreSQL warehouse
-- ============================================================

-- Keep analytical mart tables separate from raw landing tables.
CREATE SCHEMA IF NOT EXISTS mart;

COMMENT ON SCHEMA mart IS
'Analytical serving layer containing dimensional and fact tables.';
