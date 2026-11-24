
import pandas as pd
from sqlalchemy import inspect

from src.config import ECOM_TABLES, EXTRACTION_CHUNK_SIZE
from src.db import get_ecom_engine


def extract_ecom_tables():
    """
    Extract only the selected E-commerce tables in chunks.
    """

    engine = get_ecom_engine()

    try:
        inspector = inspect(engine)
        available_tables = set(
            inspector.get_table_names(schema="ecom")
        )

        missing_tables = set(ECOM_TABLES) - available_tables

        if missing_tables:
            raise ValueError(
                f"Selected E-commerce tables not found: "
                f"{sorted(missing_tables)}"
            )

        print(
            f"E-commerce tables selected: {len(ECOM_TABLES)}"
        )

        for table in ECOM_TABLES:
            print(f"\nExtracting: {table}")

            query = f'SELECT * FROM "ecom"."{table}"'
            table_has_rows = False

            for chunk in pd.read_sql_query(
                query,
                con=engine,
                chunksize=EXTRACTION_CHUNK_SIZE
            ):
                table_has_rows = True

                print(
                    f"  Rows extracted: {len(chunk):,}"
                )

                yield table, chunk

            if not table_has_rows:
                empty_query = (
                    f'SELECT * FROM "ecom"."{table}" LIMIT 0'
                )

                empty_df = pd.read_sql_query(
                    empty_query,
                    con=engine
                )

                print("  Table is empty; preserving its columns.")

                yield table, empty_df

    finally:
        engine.dispose()
