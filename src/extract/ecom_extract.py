
import pandas as pd
from sqlalchemy import MetaData, Table, inspect, select, tuple_

from src.config import ECOM_TABLES, EXTRACTION_CHUNK_SIZE
from src.db import get_ecom_engine


def extract_ecom_tables():
    """
    Extract selected E-commerce tables using keyset pagination.

    Each page uses a short-lived source connection.
    Pagination uses the complete primary key, including
    composite primary keys.
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

        for table_name in ECOM_TABLES:
            print(f"\nExtracting: {table_name}")

            primary_key_info = inspector.get_pk_constraint(
                table_name,
                schema="ecom"
            )

            primary_key_columns = (
                primary_key_info.get("constrained_columns") or []
            )

            if not primary_key_columns:
                raise ValueError(
                    f"No primary key found for ecom.{table_name}."
                )

            source_table = Table(
                table_name,
                MetaData(),
                schema="ecom",
                autoload_with=engine
            )

            key_columns = [
                source_table.c[column]
                for column in primary_key_columns
            ]

            statement = select(source_table).order_by(*key_columns)

            last_values = None
            table_has_rows = False

            while True:

                page_query = statement

                # Start after the last primary-key value
                # retrieved from the previous page.
                if last_values is not None:

                    if len(key_columns) == 1:
                        page_query = page_query.where(
                            key_columns[0] > last_values[0]
                        )
                    else:
                        page_query = page_query.where(
                            tuple_(*key_columns) > tuple_(*last_values)
                        )

                page_query = page_query.limit(
                    EXTRACTION_CHUNK_SIZE
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

                # Save the complete primary key of the last row.
                last_row = chunk.iloc[-1]

                last_values = [
                    last_row[column].item()
                    if hasattr(last_row[column], "item")
                    else last_row[column]
                    for column in primary_key_columns
                ]

                yield table_name, chunk

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
