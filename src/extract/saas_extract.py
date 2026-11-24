
import pandas as pd
from sqlalchemy import MetaData, Table, inspect, select

from src.config import SAAS_TABLES, EXTRACTION_CHUNK_SIZE
from src.db import get_saas_engine


def extract_saas_tables():
    """
    Extract selected SaaS tables in pages.

    Each page is fetched using a short-lived source connection.
    Rows are ordered by primary key to ensure deterministic pagination.
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

        for table_name in SAAS_TABLES:
            print(f"\nExtracting: {table_name}")

            # Retrieve the table's primary-key columns.
            primary_key_info = inspector.get_pk_constraint(
                table_name,
                schema="saas"
            )

            primary_key_columns = (
                primary_key_info.get("constrained_columns") or []
            )

            if not primary_key_columns:
                raise ValueError(
                    f"No primary key found for saas.{table_name}. "
                    "Deterministic pagination requires a primary key."
                )

            # Reflect the source table structure.
            source_table = Table(
                table_name,
                MetaData(),
                schema="saas",
                autoload_with=engine
            )

            # Build an ordered query using every primary-key column.
            statement = (
                select(source_table)
                .order_by(
                    *[
                        source_table.c[column]
                        for column in primary_key_columns
                    ]
                )
            )

            offset = 0
            table_has_rows = False

            while True:

                page_query = (
                    statement
                    .limit(EXTRACTION_CHUNK_SIZE)
                    .offset(offset)
                )

                # Fetch the complete page and close the connection
                # before yielding the DataFrame to the loader.
                with engine.connect() as connection:
                    chunk = pd.read_sql_query(
                        page_query,
                        con=connection
                    )

                if chunk.empty:
                    break

                table_has_rows = True

                print(
                    f"  Rows extracted: {len(chunk):,}"
                )

                offset += len(chunk)

                yield table_name, chunk

            # Preserve the table structure when the source table
            # contains no records.
            if not table_has_rows:

                empty_query = statement.limit(0)

                with engine.connect() as connection:
                    empty_df = pd.read_sql_query(
                        empty_query,
                        con=connection
                    )

                print(
                    "  Table is empty; preserving its columns."
                )

                yield table_name, empty_df

    finally:
        engine.dispose()
