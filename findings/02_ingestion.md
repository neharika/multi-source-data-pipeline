# Ingestion Pipeline Findings

## Overview

Milestone 3 implemented polling-based snapshot reconciliation for the E-commerce and SaaS source databases. The pipeline uses keyset pagination, logical primary keys, SHA-256 row hashes, and persistent row-state tracking to detect inserts, updates, and deletes.

The initial reconciliation processed 17 tables and inserted 1,011,809 records into the raw target schemas.

## Initial Ingestion Results

| Source table | Rows inserted |
|---|---:|
| E-commerce: orders | 40,000 |
| E-commerce: order_items | 81,806 |
| E-commerce: order_status_history | 158,414 |
| E-commerce: customers | 10,000 |
| E-commerce: products | 4,000 |
| E-commerce: payment_transactions | 40,034 |
| E-commerce: shipments | 32,089 |
| E-commerce: sessions | 100,000 |
| E-commerce: session_events | 292,903 |
| E-commerce: attribution_touches | 100,000 |
| E-commerce: devices | 85,168 |
| **E-commerce total** | **944,414** |
| SaaS: events | 53,534 |
| SaaS: subscriptions | 2,113 |
| SaaS: subscription_events | 3,741 |
| SaaS: invoices | 4,201 |
| SaaS: users | 2,556 |
| SaaS: accounts | 1,250 |
| **SaaS total** | **67,395** |
| **Overall total** | **1,011,809** |

## Idempotency and Change Detection

A second full reconciliation processed all 1,011,809 records as unchanged. It produced zero inserts, zero updates, and zero deletions, confirming idempotent behaviour across all 17 tables.

UPDATE detection was verified using the isolated ingestion test fixture. A changed row hash was classified as an update.

DELETE detection was also verified using the test fixture. A record absent from the simulated source scan was removed from both the target table and row-state tracking.

## Watermark Persistence and Lag

All 17 successful table checkpoints were persisted in `control.ingestion_watermarks`.

At the verification query, the most recent E-commerce checkpoint was approximately 4 minutes 51 seconds old, while the most recent SaaS checkpoint was approximately 2 minutes 59 seconds old.

Because the sources do not expose reliable modification timestamps, watermark columns and values remain NULL. The checkpoint records the last successful reconciliation time rather than a source-data timestamp.

## Late-Arriving Records

A test record with a business timestamp of March 15, 2026 was successfully discovered and inserted during reconciliation. This confirms that older business timestamps do not exclude late-arriving records from full-snapshot scans.

## CDC Coverage and Limitations

Native log-based CDC was not available because the source database roles lack replication privileges and the tables do not expose reliable change logs or consistent `updated_at` columns.

The implemented solution uses polling-based full-snapshot reconciliation instead. It detects inserts and updates through row hashes and deletes through source/target key comparison. Scans are not transactionally consistent across an entire source table, so changes occurring during a scan may be detected on a subsequent run.
