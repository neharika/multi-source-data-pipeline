
import pandas as pd
from sqlalchemy import MetaData, Table, inspect, select

from src.config import SAAS_TABLES, EXTRACTION_CHUNK_SIZE
from src.db import get_saas_engine


def extract_saas_tables():
    """
    Extract selected SaaS tables using keyset pagination.

    Each page uses a short-lived source connection.
    Pagination uses the table's primary key.
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

            # Retrieve the table's primary-key column.
            primary_key_info = inspector.get_pk_constraint(
                table_name,
                schema="saas"
            )

            primary_key_columns = (
                primary_key_info.get("constrained_columns") or []
            )

            if not primary_key_columns:
                raise ValueError(
                    f"No primary key found for saas.{table_name}."
                )

            source_table = Table(
                table_name,
                MetaData(),
                schema="saas",
                autoload_with=engine
            )

            key_column = source_table.c[
                primary_key_columns[0]
            ]

            statement = (
                select(source_table)
                .order_by(key_column)
            )

            last_value = None
            table_has_rows = False

            while True:

                page_query = statement

                # Continue after the last primary-key value
                # retrieved from the previous page.
                if last_value is not None:
                    page_query = page_query.where(
                        key_column > last_value
                    )

                page_query = page_query.limit(
                    EXTRACTION_CHUNK_SIZE
                )

                # Fetch the page and close the source connection
                # before yielding data to the loader.
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

                # Convert NumPy scalar values into native
                # Python values for database compatibility.
                value = chunk.iloc[-1][primary_key_columns[0]]

                last_value = (
                    value.item()
                    if hasattr(value, "item")
                    else value
                )

                yield table_name, chunk

            # Preserve the table structure when it contains no rows.
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
