
import json

from psycopg2.extras import execute_values
from sqlalchemy import text

from src.config import (
    LOAD_CHUNK_SIZE,
    ECOM_TABLES,
    SAAS_TABLES,
    ECOM_PRIMARY_KEYS,
    SAAS_PRIMARY_KEYS,
)
from src.db import get_target_engine


def prepare_records(chunk):
    """
    Convert a DataFrame chunk into PostgreSQL-compatible records.
    Preserve column order and convert missing values to None.
    """

    if chunk.empty:
        return [], list(chunk.columns)

    clean_chunk = chunk.astype(object).where(chunk.notna(), None)

    records = list(
        clean_chunk.itertuples(index=False, name=None)
    )

    return records, list(chunk.columns)


def upsert_chunk(
    source_schema,
    target_schema,
    table_name,
    chunk,
    key_columns,
):
    """
    Classify incoming rows, upsert only inserts and updates,
    and update reconciliation state atomically.

    Supported production mappings:
        ecom -> raw_ecom
        saas -> raw_saas

    Supported test mapping:
        test -> control.ingestion_test_orders
    """

    from src.ingest.reconciliation import (
        serialize_primary_key,
        hash_row,
    )

    # --------------------------------------------------
    # 1. Validate the source and target mapping
    # --------------------------------------------------

    if source_schema == "test":
        expected_target = "control"
        allowed_tables = {"ingestion_test_orders"}
        primary_keys = {
            "ingestion_test_orders": ["order_id"]
        }

    else:
        allowed_targets = {
            "ecom": (
                "raw_ecom",
                ECOM_TABLES,
                ECOM_PRIMARY_KEYS,
            ),
            "saas": (
                "raw_saas",
                SAAS_TABLES,
                SAAS_PRIMARY_KEYS,
            ),
        }

        if source_schema not in allowed_targets:
            raise ValueError("Unsupported source schema.")

        expected_target, allowed_tables, primary_keys = (
            allowed_targets[source_schema]
        )

    if target_schema != expected_target:
        raise ValueError(
            "Invalid source and target schema combination."
        )

    if table_name not in allowed_tables:
        raise ValueError(f"Unsupported table: {table_name}")

    if key_columns != primary_keys[table_name]:
        raise ValueError("Primary key configuration mismatch.")

    if not key_columns:
        raise ValueError("At least one primary key is required.")

    if chunk.empty:
        return {
            "inserted": 0,
            "updated": 0,
            "unchanged": 0,
        }

    # --------------------------------------------------
    # 2. Validate incoming columns
    # --------------------------------------------------

    missing_keys = [
        column for column in key_columns
        if column not in chunk.columns
    ]

    if missing_keys:
        raise ValueError(
            f"Missing primary key columns: {missing_keys}"
        )

    if len(set(chunk.columns)) != len(chunk.columns):
        raise ValueError("Duplicate column names in incoming chunk.")

    records, columns = prepare_records(chunk)

    row_data = chunk.to_dict(orient="records")

    # --------------------------------------------------
    # 3. Prepare primary keys and row hashes
    # --------------------------------------------------

    payload = []
    row_lookup = {}

    for row, record in zip(row_data, records):

        primary_key = json.loads(
            serialize_primary_key(row, key_columns)
        )

        key_token = json.dumps(
            primary_key,
            sort_keys=True,
            separators=(",", ":"),
        )

        if key_token in row_lookup:
            raise ValueError(
                f"Duplicate primary key in chunk: {key_token}"
            )

        row_hash = hash_row(row)

        payload.append({
            "primary_key": primary_key,
            "row_hash": row_hash,
        })

        row_lookup[key_token] = record

    payload_json = json.dumps(
        payload,
        default=str,
        separators=(",", ":"),
    )

    # --------------------------------------------------
    # 4. Prepare reconciliation state rows
    # --------------------------------------------------

    # This must happen for ALL rows, including unchanged rows.
    state_rows = []

    for item in payload:
        state_rows.append((
            source_schema,
            table_name,
            json.dumps(item["primary_key"]),
            item["row_hash"],
        ))

    # --------------------------------------------------
    # 5. Start one atomic database transaction
    # --------------------------------------------------

    engine = get_target_engine()

    try:
        with engine.begin() as conn:

            # ------------------------------------------
            # 5a. Classify incoming rows
            # ------------------------------------------

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

                key_token = json.dumps(
                    result["primary_key"],
                    sort_keys=True,
                    separators=(",", ":"),
                )

                classified[result["action"]].append(key_token)

            # ------------------------------------------
            # 5b. Identify only changed records
            # ------------------------------------------

            changed_keys = (
                classified["INSERT"] + classified["UPDATE"]
            )

            changed_records = [
                row_lookup[key]
                for key in changed_keys
            ]

            # ------------------------------------------
            # 5c. Build the raw-table upsert query
            # ------------------------------------------

            preparer = engine.dialect.identifier_preparer

            quoted_schema = preparer.quote(target_schema)
            quoted_table = preparer.quote(table_name)

            quoted_columns = ", ".join(
                preparer.quote(column)
                for column in columns
            )

            quoted_keys = ", ".join(
                preparer.quote(column)
                for column in key_columns
            )

            update_columns = [
                column for column in columns
                if column not in key_columns
            ]

            if update_columns:

                update_clause = ", ".join(
                    f"{preparer.quote(column)} = "
                    f"EXCLUDED.{preparer.quote(column)}"
                    for column in update_columns
                )

                conflict_action = (
                    f"DO UPDATE SET {update_clause}"
                )

            else:
                conflict_action = "DO NOTHING"

            insert_query = (
                f"INSERT INTO {quoted_schema}.{quoted_table} "
                f"({quoted_columns}) VALUES %s "
                f"ON CONFLICT ({quoted_keys}) {conflict_action}"
            )

            # ------------------------------------------
            # 5d. Upsert only INSERT and UPDATE rows
            # ------------------------------------------

            raw_conn = conn.connection.driver_connection

            if changed_records:

                with raw_conn.cursor() as cursor:

                    for start in range(
                        0,
                        len(changed_records),
                        LOAD_CHUNK_SIZE,
                    ):

                        batch = changed_records[
                            start:start + LOAD_CHUNK_SIZE
                        ]

                        execute_values(
                            cursor,
                            insert_query,
                            batch,
                            page_size=LOAD_CHUNK_SIZE,
                        )

            # ------------------------------------------
            # 5e. Update reconciliation state
            # ------------------------------------------

            state_query = """
                INSERT INTO control.ingestion_row_state (
                    source_schema,
                    table_name,
                    primary_key,
                    row_hash,
                    last_seen_at
                )
                VALUES %s
                ON CONFLICT (
                    source_schema,
                    table_name,
                    primary_key
                )
                DO UPDATE SET
                    row_hash = EXCLUDED.row_hash,
                    last_seen_at = NOW();
            """

            with raw_conn.cursor() as cursor:

                execute_values(
                    cursor,
                    state_query,
                    state_rows,
                    page_size=LOAD_CHUNK_SIZE,
                    template="(%s, %s, %s::jsonb, %s, NOW())",
                )

        # --------------------------------------------------
        # 6. Return classification counts
        # --------------------------------------------------

        return {
            "inserted": len(classified["INSERT"]),
            "updated": len(classified["UPDATE"]),
            "unchanged": len(classified["UNCHANGED"]),
        }

    finally:
        engine.dispose()
