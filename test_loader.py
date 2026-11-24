
import pandas as pd
from sqlalchemy import inspect, text

from src.db import get_ecom_engine, get_target_engine
from src.load.loaders import load_chunks


TEST_TABLES = [
    "orders",
    "product_variants",
    "sessions"
]


def test_loader():
    source_engine = get_ecom_engine()
    target_engine = get_target_engine()

    samples = []

    try:
        # Extract five sample rows from each source table.
        for table in TEST_TABLES:
            query = f'SELECT * FROM "ecom"."{table}" LIMIT 5'

            df = pd.read_sql_query(
                query,
                con=source_engine
            )

            print(f"{table}: {len(df)} source rows extracted")

            samples.append((table, df))

        # Confirm that every table returned five rows.
        for table, df in samples:
            assert len(df) == 5, (
                f"Expected five rows from {table}, "
                f"received {len(df)}"
            )

        # Use the revised project loader.
        loaded_counts = load_chunks(
            iter(samples),
            target_schema="raw_ecom",
            source_engine=source_engine,
            source_schema="ecom"
        )

        target_inspector = inspect(target_engine)

        # Verify row counts and column types.
        for table in TEST_TABLES:

            with target_engine.connect() as conn:
                target_count = conn.execute(
                    text(
                        f'SELECT COUNT(*) '
                        f'FROM "raw_ecom"."{table}"'
                    )
                ).scalar_one()

            assert target_count == 5, (
                f"Row count mismatch for {table}"
            )

            assert loaded_counts[table] == 5

            source_columns = inspect(source_engine).get_columns(
                table,
                schema="ecom"
            )

            target_columns = target_inspector.get_columns(
                table,
                schema="raw_ecom"
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
                f"Column type mismatch in {table}\n"
                f"Source: {source_types}\n"
                f"Target: {target_types}"
            )

            print(
                f"{table}: {target_count} rows loaded; "
                "column types match."
            )

        print("\nTEST PASSED: All three tables loaded successfully.")

    finally:
        # Remove test tables from the target raw schema.
        with target_engine.begin() as conn:
            for table in TEST_TABLES:
                conn.execute(
                    text(
                        f'DROP TABLE IF EXISTS "raw_ecom"."{table}"'
                    )
                )

        source_engine.dispose()
        target_engine.dispose()


if __name__ == "__main__":
    test_loader()
