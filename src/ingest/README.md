# Ingestion Strategy

## Overview

The ingestion layer supports two paths:

1. **Full refresh** — the existing pipeline in `src/main.py` extracts source tables and replaces the corresponding raw target tables. This is intended for initial loads and recovery.
2. **Snapshot reconciliation** — `run_incremental_ingestion()` in `src/ingest/cdc.py` scans source tables in keyset-paginated chunks and reconciles them with the raw target tables. This is the normal change-detection path.

The reconciliation process uses logical primary keys, SHA-256 row hashes, and persistent row-state tracking to identify inserts, updates, and deletes.

## Source-specific ingestion decisions

Both source systems use polling-based full-snapshot reconciliation.

| Source | Tables | Extraction strategy | Change-detection decision |
|---|---:|---|---|
| E-commerce (`ecom`) | 11 | Keyset-paginated full table scans | Row hashes detect inserts and updates; source/target key comparison detects deletes |
| SaaS (`saas`) | 6 | Keyset-paginated full table scans | Row hashes detect inserts and updates; source/target key comparison detects deletes |

Neither source provides a reliable `updated_at` column across its tables. Available timestamps represent business events rather than reliable modification timestamps. Examples include `created_at`, `occurred_at`, `changed_at`, `txn_time`, `event_time`, and subscription or invoice dates.

Consequently, timestamp-filtered incremental extraction would miss updates to older records. Full-snapshot reconciliation is used instead.

## Watermark strategy

The persistent checkpoint store is `control.ingestion_watermarks`.

A checkpoint is updated only after a table's source scan, target upserts, and deletion reconciliation complete successfully.

Because no reliable modification timestamp is available, `watermark_column` and `watermark_value` are stored as `NULL`. `last_successful_load` records the completion time of the most recent successful table reconciliation.

This is a successful-scan checkpoint, not a source timestamp filter.

## Row-state tracking and reconciliation

The table `control.ingestion_row_state` stores:

- Source schema and table name
- Logical primary key, including composite keys
- SHA-256 hash of the normalized row
- Last time the row was seen in a successful scan

For each extracted chunk:

- **INSERT** — no matching row-state record exists.
- **UPDATE** — a matching key exists but its row hash differs.
- **UNCHANGED** — the stored and incoming hashes match.

Inserted and updated rows are upserted into the raw target tables. Row-state changes are committed with the target upserts.

After a complete table scan, deletion reconciliation removes target rows whose keys were not seen during that scan and removes their stale row-state records. A failed or incomplete table scan does not proceed to deletion reconciliation or checkpoint advancement.

## Late-arriving records

Full-snapshot scans do not filter records by their business timestamps. A record arriving late with an older `created_at`, `occurred_at`, or other event timestamp is therefore eligible for ingestion during the next scan.

This behaviour was verified using a test record with a March 2026 business timestamp.

## CDC coverage and limitations

Native CDC or log-based change capture is not available with the current source database permissions. The source roles do not have the required replication privileges, and the source tables do not expose a reliable change log.

The implemented approach provides polling-based detection of inserts, updates, and deletes through snapshot reconciliation. It should not be described as native CDC.

A scan is not a transactionally consistent snapshot across the entire source table. Changes made while a scan is running may be observed on a later run. Reconciliation should therefore run regularly, with the next successful scan providing another opportunity to detect those changes.
