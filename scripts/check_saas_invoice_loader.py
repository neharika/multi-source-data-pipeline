"""
MANUAL INTEGRATION CHECK — NOT SAFE FOR AUTOMATED TEST DISCOVERY

This script reloads and replaces raw_saas.invoices
in the configured target warehouse.

Run only when an intentional replacement is acceptable.
"""

import pandas as pd
from sqlalchemy import inspect, text

from src.config import EXTRACTION_CHUNK_SIZE
from src.db import get_saas_engine, get_target_engine
from src.load.loaders import load_chunks


def test_saas_invoice_loader():

    source_engine = get_saas_engine()
    target_engine = get_target_engine()

    try:
        source_inspector = inspect(source_engine)

        # Identify the source primary key.
        primary_key_info = source_inspector.get_pk_constraint(
            "invoices",
            schema="saas"
        )

        primary_key = primary_key_info["constrained_columns"][0]

        # Extract invoices using keyset pagination.
        chunks = []

        with source_engine.connect() as conn:

            source_count = conn.execute(
                text("SELECT COUNT(*) FROM saas.invoices")
            ).scalar_one()

            last_value = None

            while True:

                query = (
                    f'SELECT * FROM "saas"."invoices" '
                    + (
                        f'WHERE "{primary_key}" > :last_value '
                        if last_value is not None else ""
                    )
                    + f'ORDER BY "{primary_key}" '
                    f'LIMIT :chunk_size'
                )

                params = {
                    "chunk_size": EXTRACTION_CHUNK_SIZE
                }

                if last_value is not None:
                    params["last_value"] = last_value

                df = pd.read_sql_query(
                    text(query),
                    con=conn,
                    params=params
                )

                if df.empty:
                    break

                value = df.iloc[-1][primary_key]

                last_value = (
                    value.item()
                    if hasattr(value, "item")
                    else value
                )

                print(f"  Extracted: {len(df):,} invoices")

                chunks.append(("invoices", df))

        print(f"\nSource invoices: {source_count:,}")

        # Load invoices using the revised staging loader.
        loaded_counts = load_chunks(
            iter(chunks),
            target_schema="raw_saas",
            source_engine=source_engine,
            source_schema="saas"
        )

        # Verify target row count.
        with target_engine.connect() as conn:
            target_count = conn.execute(
                text("SELECT COUNT(*) FROM raw_saas.invoices")
            ).scalar_one()

        assert target_count == source_count, (
            f"Row count mismatch: source={source_count}, "
            f"target={target_count}"
        )

        assert loaded_counts["invoices"] == source_count

        # Compare source and target column types.
        target_inspector = inspect(target_engine)

        source_columns = source_inspector.get_columns(
            "invoices",
            schema="saas"
        )

        target_columns = target_inspector.get_columns(
            "invoices",
            schema="raw_saas"
        )

        source_types = {
            col["name"]: type(col["type"]).__name__
            for col in source_columns
        }

        target_types = {
            col["name"]: type(col["type"]).__name__
            for col in target_columns
        }

        assert source_types == target_types, (
            f"Column type mismatch:\n"
            f"Source: {source_types}\n"
            f"Target: {target_types}"
        )

        print(f"\nTarget invoices: {target_count:,}")
        print("Column types match.")
        print("\nTEST PASSED: SaaS invoices loaded successfully.")

    finally:
        source_engine.dispose()
        target_engine.dispose()


if __name__ == "__main__":
    test_saas_invoice_loader()
