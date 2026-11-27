
from sqlalchemy import text

from src.db import get_target_engine


def initialize_watermark_store():
    """Create the persistent watermark table if it does not exist."""

    engine = get_target_engine()

    try:
        with engine.begin() as conn:
            conn.execute(text("""
                CREATE SCHEMA IF NOT EXISTS control;
            """))

            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS control.ingestion_watermarks (
                    source_schema TEXT NOT NULL,
                    table_name TEXT NOT NULL,
                    watermark_column TEXT,
                    watermark_value TIMESTAMPTZ,
                    last_successful_load TIMESTAMPTZ,
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    PRIMARY KEY (source_schema, table_name)
                );
            """))

        print("Watermark store initialized successfully.")

    finally:
        engine.dispose()


def get_watermark(source_schema, table_name):
    """Retrieve the last successfully processed watermark."""

    engine = get_target_engine()

    try:
        with engine.connect() as conn:
            result = conn.execute(
                text("""
                    SELECT watermark_column, watermark_value
                    FROM control.ingestion_watermarks
                    WHERE source_schema = :source_schema
                      AND table_name = :table_name;
                """),
                {
                    "source_schema": source_schema,
                    "table_name": table_name,
                },
            ).mappings().first()

        if result is None:
            return None, None

        return result["watermark_column"], result["watermark_value"]

    finally:
        engine.dispose()


def update_watermark(
    source_schema,
    table_name,
    watermark_column,
    watermark_value,
):
    """
    Insert or update watermark state.

    Call only after the corresponding target load succeeds.
    """

    engine = get_target_engine()

    try:
        with engine.begin() as conn:
            conn.execute(
                text("""
                    INSERT INTO control.ingestion_watermarks (
                        source_schema,
                        table_name,
                        watermark_column,
                        watermark_value,
                        last_successful_load,
                        updated_at
                    )
                    VALUES (
                        :source_schema,
                        :table_name,
                        :watermark_column,
                        :watermark_value,
                        NOW(),
                        NOW()
                    )
                    ON CONFLICT (source_schema, table_name)
                    DO UPDATE SET
                        watermark_column = EXCLUDED.watermark_column,
                        watermark_value = EXCLUDED.watermark_value,
                        last_successful_load = NOW(),
                        updated_at = NOW();
                """),
                {
                    "source_schema": source_schema,
                    "table_name": table_name,
                    "watermark_column": watermark_column,
                    "watermark_value": watermark_value,
                },
            )

        print(
            f"Watermark updated: "
            f"{source_schema}.{table_name}"
        )

    finally:
        engine.dispose()
