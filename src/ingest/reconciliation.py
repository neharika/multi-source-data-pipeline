from sqlalchemy import text
from src.db import get_target_engine

import hashlib
import json

from datetime import date, datetime
from decimal import Decimal


def serialize_primary_key(row, key_columns):
    """Serialize a single or composite logical key consistently."""

    key = {
        column: row[column]
        for column in key_columns
    }

    return json.dumps(
        key,
        sort_keys=True,
        default=str,
        separators=(",", ":"),
    )


def hash_row(row):
    """Generate a deterministic SHA-256 hash for a source row."""

    normalized = {}

    for column, value in row.items():

        if isinstance(value, (datetime, date)):
            value = value.isoformat()

        elif isinstance(value, Decimal):
            value = str(value)

        elif isinstance(value, bytes):
            value = value.hex()

        normalized[column] = value

    serialized = json.dumps(
        normalized,
        sort_keys=True,
        default=str,
        separators=(",", ":"),
        ensure_ascii=False,
    )

    return hashlib.sha256(
        serialized.encode("utf-8")
    ).hexdigest()

def classify_row(source_schema, table_name, row, key_columns):
    """
    Compare a source row with its stored hash.

    Returns INSERT, UPDATE, or UNCHANGED.
    """
    primary_key = serialize_primary_key(row, key_columns)
    current_hash = hash_row(row)

    engine = get_target_engine()

    try:
        with engine.connect() as conn:
            result = conn.execute(
                text("""
                    SELECT row_hash
                    FROM control.ingestion_row_state
                    WHERE source_schema = :source_schema
                      AND table_name = :table_name
                      AND primary_key = CAST(:primary_key AS JSONB);
                """),
                {
                    "source_schema": source_schema,
                    "table_name": table_name,
                    "primary_key": primary_key,
                },
            ).scalar_one_or_none()

        if result is None:
            return "INSERT"

        if result != current_hash:
            return "UPDATE"

        return "UNCHANGED"

    finally:
        engine.dispose()

def classify_chunk(source_schema, table_name, chunk, key_columns):
    """
    Classify a DataFrame chunk as INSERT, UPDATE, or UNCHANGED.

    Uses one target database query for the entire chunk.
    """

    if chunk.empty:
        return {
            "INSERT": [],
            "UPDATE": [],
            "UNCHANGED": [],
        }

    records = chunk.to_dict(orient="records")

    payload = []

    for row in records:
        payload.append({
            "primary_key": json.loads(
                serialize_primary_key(row, key_columns)
            ),
            "row_hash": hash_row(row),
        })

    payload_json = json.dumps(
        payload,
        default=str,
        separators=(",", ":"),
    )

    engine = get_target_engine()

    try:
        with engine.connect() as conn:
            results = conn.execute(
                text("""
                    WITH incoming AS (
                        SELECT
                            item->'primary_key' AS primary_key,
                            item->>'row_hash' AS row_hash
                        FROM jsonb_array_elements(
                            CAST(:payload AS JSONB)
                        ) AS item
                    )
                    SELECT
                        incoming.primary_key,
                        CASE
                            WHEN stored.row_hash IS NULL
                                THEN 'INSERT'
                            WHEN stored.row_hash <> incoming.row_hash
                                THEN 'UPDATE'
                            ELSE 'UNCHANGED'
                        END AS action
                    FROM incoming
                    LEFT JOIN control.ingestion_row_state AS stored
                        ON stored.source_schema = :source_schema
                       AND stored.table_name = :table_name
                       AND stored.primary_key = incoming.primary_key;
                """),
                {
                    "payload": payload_json,
                    "source_schema": source_schema,
                    "table_name": table_name,
                },
            ).mappings().all()

        classified = {
            "INSERT": [],
            "UPDATE": [],
            "UNCHANGED": [],
        }

        for result in results:
            classified[result["action"]].append(
                result["primary_key"]
            )

        return classified

    finally:
        engine.dispose()

def get_scan_marker():
    """Get a scan marker from the target database clock."""

    engine = get_target_engine()

    try:
        with engine.connect() as conn:
            return conn.execute(
                text("SELECT clock_timestamp()")
            ).scalar_one()

    finally:
        engine.dispose()


def reconcile_deletions(source_schema, table_name, scan_started_at):
    """
    Remove target rows absent from a successfully completed
    full source scan.
    """

    from src.config import ECOM_PRIMARY_KEYS, SAAS_PRIMARY_KEYS

    allowed_mappings = {
    "ecom": ("raw_ecom", ECOM_PRIMARY_KEYS),
    "saas": ("raw_saas", SAAS_PRIMARY_KEYS),
    "test": (
        "control",
        {"ingestion_test_orders": ["order_id"]},
    ),
}

    if source_schema not in allowed_mappings:
        raise ValueError(f"Unsupported source schema: {source_schema}")

    target_schema, primary_keys = allowed_mappings[source_schema]

    if table_name not in primary_keys:
        raise ValueError(f"Unsupported table: {table_name}")

    key_columns = primary_keys[table_name]

    engine = get_target_engine()

    try:
        preparer = engine.dialect.identifier_preparer

        quoted_schema = preparer.quote(target_schema)
        quoted_table = preparer.quote(table_name)

        quoted_keys = [
            preparer.quote(column)
            for column in key_columns
        ]

        key_conditions = " AND ".join(
            f"target.{column} = key_row.{column}"
            for column in quoted_keys
        )

        with engine.begin() as conn:

            result = conn.execute(
                text(f"""
                    DELETE FROM {quoted_schema}.{quoted_table} AS target
                    WHERE NOT EXISTS (
                        SELECT 1
                        FROM control.ingestion_row_state AS state
                        CROSS JOIN LATERAL
                            jsonb_populate_record(
                                NULL::{quoted_schema}.{quoted_table},
                                state.primary_key
                            ) AS key_row
                        WHERE state.source_schema = :source_schema
                          AND state.table_name = :table_name
                          AND state.last_seen_at >= :scan_started_at
                          AND {key_conditions}
                    );
                """),
                {
                    "source_schema": source_schema,
                    "table_name": table_name,
                    "scan_started_at": scan_started_at,
                },
            )

            deleted_count = result.rowcount

            # Remove stale state records after reconciliation.
            conn.execute(
                text("""
                    DELETE FROM control.ingestion_row_state
                    WHERE source_schema = :source_schema
                      AND table_name = :table_name
                      AND last_seen_at < :scan_started_at;
                """),
                {
                    "source_schema": source_schema,
                    "table_name": table_name,
                    "scan_started_at": scan_started_at,
                },
            )

        return deleted_count

    finally:
        engine.dispose()
