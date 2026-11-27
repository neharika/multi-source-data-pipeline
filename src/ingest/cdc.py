
from src.config import ECOM_PRIMARY_KEYS, SAAS_PRIMARY_KEYS

from src.extract.ecom_extract import extract_ecom_tables
from src.extract.saas_extract import extract_saas_tables

from src.ingest.loaders import upsert_chunk
from src.ingest.reconciliation import (
    get_scan_marker,
    reconcile_deletions,
)
from src.ingest.watermark import (
    initialize_watermark_store,
    update_watermark,
)


def process_source(source_schema, target_schema, extractor, primary_keys):
    """Stream and reconcile each table from one source database."""

    summary = {}
    current_table = None
    scan_started_at = None
    counts = None

    def finish_table(table_name, marker, table_counts):
        deleted = reconcile_deletions(
            source_schema=source_schema,
            table_name=table_name,
            scan_started_at=marker,
        )

        update_watermark(
            source_schema=source_schema,
            table_name=table_name,
            watermark_column=None,
            watermark_value=None,
        )

        table_counts["deleted"] = deleted
        summary[table_name] = table_counts

        print(f"  Results: {table_counts}")

    for table_name, chunk in extractor():

        if table_name != current_table:

            if current_table is not None:
                finish_table(
                    current_table,
                    scan_started_at,
                    counts,
                )

            current_table = table_name
            scan_started_at = get_scan_marker()

            counts = {
                "inserted": 0,
                "updated": 0,
                "unchanged": 0,
            }

            print(f"\nProcessing {source_schema}.{table_name}")

        result = upsert_chunk(
            source_schema=source_schema,
            target_schema=target_schema,
            table_name=table_name,
            chunk=chunk,
            key_columns=primary_keys[table_name],
        )

        for key in counts:
            counts[key] += result[key]

    if current_table is not None:
        finish_table(
            current_table,
            scan_started_at,
            counts,
        )

    return summary


def run_incremental_ingestion():
    """Run full-snapshot reconciliation for both source systems."""

    print("\nInitializing incremental ingestion...")
    initialize_watermark_store()

    print("\nStarting E-commerce reconciliation...")

    ecom_summary = process_source(
        source_schema="ecom",
        target_schema="raw_ecom",
        extractor=extract_ecom_tables,
        primary_keys=ECOM_PRIMARY_KEYS,
    )

    print("\nStarting SaaS reconciliation...")

    saas_summary = process_source(
        source_schema="saas",
        target_schema="raw_saas",
        extractor=extract_saas_tables,
        primary_keys=SAAS_PRIMARY_KEYS,
    )

    print("\nIncremental ingestion completed.")

    return {
        "ecom": ecom_summary,
        "saas": saas_summary,
    }
