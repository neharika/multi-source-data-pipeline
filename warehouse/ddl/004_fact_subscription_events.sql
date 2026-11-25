
-- ============================================================
-- File: 004_fact_subscription_events.sql
-- Purpose: Create the SaaS subscription event fact table.
-- Schema: mart
--
-- Grain:
-- One row per unique SaaS subscription event,
-- identified by event_id.
-- ============================================================

CREATE TABLE IF NOT EXISTS mart.fact_subscription_events (

    -- Source-system event identifier.
    event_id INTEGER,

    -- Foreign key to the SaaS account's customer dimension record.
    customer_sk BIGINT NOT NULL,

    -- Source-system identifiers.
    subscription_id INTEGER,
    user_id INTEGER,
    actor_user_id INTEGER,

    -- Event details.
    event_type TEXT,
    event_time TIMESTAMP WITHOUT TIME ZONE,
    from_plan TEXT,
    to_plan TEXT,

    -- Subscription change measures.
    mrr_delta NUMERIC,
    seats_delta INTEGER,

    -- Fact-table primary key.
    CONSTRAINT pk_fact_subscription_events
        PRIMARY KEY (event_id),

    -- Link each event to its SaaS account dimension record.
    CONSTRAINT fk_fact_subscription_events_customer
        FOREIGN KEY (customer_sk)
        REFERENCES mart.dim_customer (customer_sk)
);

-- Support account-level subscription event analysis.
CREATE INDEX IF NOT EXISTS idx_fact_subscription_events_customer
ON mart.fact_subscription_events (customer_sk);

-- Support time-based event analysis.
CREATE INDEX IF NOT EXISTS idx_fact_subscription_events_time
ON mart.fact_subscription_events (event_time);

-- Support subscription-level event analysis.
CREATE INDEX IF NOT EXISTS idx_fact_subscription_events_subscription
ON mart.fact_subscription_events (subscription_id);

-- Document the table grain.
COMMENT ON TABLE mart.fact_subscription_events IS
'Grain: One row per unique SaaS subscription event, identified by event_id.';
