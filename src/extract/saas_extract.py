
import pandas as pd
from sqlalchemy import inspect

from src.config import SAAS_TABLES, EXTRACTION_CHUNK_SIZE
from src.db import get_saas_engine


def extract_saas_tables():
    """
    Extract only the selected SaaS tables in chunks.
    """

    engine = get_saas_engine()

    try:
        inspector = inspect(engine)
        available_tables = set(
            inspector.get_table_names(schema="saas")
        )

        missing_tables = set(SAAS_TABLES) - available_tables

        if missing_tables:
            raise ValueError(
                f"Selected SaaS tables not found: "
                f"{sorted(missing_tables)}"
            )

        print(
            f"SaaS tables selected: {len(SAAS_TABLES)}"
        )

        for table in SAAS_TABLES:
            print(f"\nExtracting: {table}")

            query = f'SELECT * FROM "saas"."{table}"'
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
                    f'SELECT * FROM "saas"."{table}" LIMIT 0'
                )

                empty_df = pd.read_sql_query(
                    empty_query,
                    con=engine
                )

                print("  Table is empty; preserving its columns.")

                yield table, empty_df

    finally:
        engine.dispose()
