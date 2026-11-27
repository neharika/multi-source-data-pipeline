from psycopg2.extras import execute_values
from sqlalchemy import Column, MetaData, Table, inspect, text

from src.config import (
    LOAD_CHUNK_SIZE,
    ECOM_PRIMARY_KEYS,
    SAAS_PRIMARY_KEYS,
)
from src.db import get_target_engine


def load_chunks(chunks, target_schema, source_engine, source_schema):
    """
    Load source DataFrame chunks into staging tables.

    Replace existing target tables only after the staging
    table has been loaded and its row count verified.

    Source column types and nullability are preserved.
    Logical primary-key indexes are recreated after replacement.
    """

    # Validate source-to-target schema mapping.
    allowed_mappings = {
        "ecom": ("raw_ecom", ECOM_PRIMARY_KEYS),
        "saas": ("raw_saas", SAAS_PRIMARY_KEYS),
    }

    if source_schema not in allowed_mappings:
        raise ValueError(
            f"Unsupported source schema: {source_schema}"
        )

    expected_target, primary_keys = allowed_mappings[source_schema]

    if target_schema != expected_target:
        raise ValueError(
            f"Invalid target schema for {source_schema}: "
            f"expected {expected_target}, received {target_schema}"
        )

    engine = get_target_engine()
    source_inspector = inspect(source_engine)

    loaded_counts = {}

    active_table_name = None
    staging_table = None

    def finalize_table(table_name, stage_table):
        """Verify staging data and atomically replace the target table."""

        staging_name = stage_table.name

        count_query = text(
            f'SELECT COUNT(*) FROM "{target_schema}"."{staging_name}"'
        )

        with engine.connect() as conn:
            staged_count = conn.execute(count_query).scalar_one()

        expected_count = loaded_counts[table_name]

        if staged_count != expected_count:
            raise RuntimeError(
                f"Staging row count mismatch for {table_name}: "
                f"expected {expected_count}, found {staged_count}"
            )

        print(
            f"\nStaging validation passed: "
            f"{target_schema}.{table_name} "
            f"({staged_count:,} rows)"
        )

        # PostgreSQL transactional DDL makes replacement and
        # index creation atomic.
        with engine.begin() as conn:

            # Remove the existing target table.
            conn.execute(
                text(
                    f'DROP TABLE IF EXISTS '
                    f'"{target_schema}"."{table_name}"'
                )
            )

            # Publish the staging table under the original name.
            conn.execute(
                text(
                    f'ALTER TABLE "{target_schema}"."{staging_name}" '
                    f'RENAME TO "{table_name}"'
                )
            )

            # Recreate the logical primary-key index.
            key_columns = primary_keys.get(table_name)

            if not key_columns:
                raise ValueError(
                    f"No primary key configuration found for {table_name}"
                )

            preparer = engine.dialect.identifier_preparer

            index_name = preparer.quote(
                f"uq_{table_name}_logical_pk"
            )
            quoted_target = preparer.quote(table_name)
            quoted_schema = preparer.quote(target_schema)

            quoted_keys = ", ".join(
                preparer.quote(column)
                for column in key_columns
            )

            conn.execute(
                text(
                    f"CREATE UNIQUE INDEX {index_name} "
                    f"ON {quoted_schema}.{quoted_target} "
                    f"({quoted_keys})"
                )
            )

        print(
            f"Published target table: "
            f"{target_schema}.{table_name}"
        )

        print(
            f"Recreated unique index on: "
            f"{target_schema}.{table_name}"
        )

    try:
        for table_name, df in chunks:

            if df is None:
                continue

            # Finalize the previous table when extraction moves
            # to the next table.
            if table_name != active_table_name:

                if active_table_name is not None:
                    finalize_table(
                        active_table_name,
                        staging_table
                    )

                # Validate that this table has a primary-key definition.
                if table_name not in primary_keys:
                    raise ValueError(
                        f"No primary key configuration found for {table_name}"
                    )

                print(
                    f"\nPreparing staging table for: "
                    f"{target_schema}.{table_name}"
                )

                source_columns = source_inspector.get_columns(
                    table_name,
                    schema=source_schema
                )

                metadata = MetaData()

                columns = [
                    Column(
                        column_info["name"],
                        column_info["type"],
                        nullable=column_info["nullable"]
                    )
                    for column_info in source_columns
                ]

                staging_name = f"{table_name}__staging"

                staging_table = Table(
                    staging_name,
                    metadata,
                    *columns,
                    schema=target_schema
                )

                # Remove any leftover staging table from an
                # earlier unsuccessful run.
                staging_table.drop(engine, checkfirst=True)
                staging_table.create(engine)

                loaded_counts[table_name] = 0
                active_table_name = table_name

            if df.empty:
                print("Empty source table; staging structure created.")
                continue

            print(
                f"Loading {target_schema}.{table_name} staging: "
                f"{len(df):,} rows"
            )

            clean_df = df.astype(object).where(df.notna(), None)

            # Build a safely quoted INSERT statement using source columns.
            preparer = engine.dialect.identifier_preparer

            quoted_schema = preparer.quote(target_schema)
            quoted_table = preparer.quote(staging_name)

            column_names = [
                column_info["name"] for column_info in source_columns
            ]

            quoted_columns = ", ".join(
                preparer.quote(column_name)
                for column_name in column_names
            )

            insert_query = (
                f"INSERT INTO {quoted_schema}.{quoted_table} "
                f"({quoted_columns}) VALUES %s"
            )

            # Load all batches for this staging table in one transaction.
            with engine.begin() as conn:

                conn.execute(
                    text("SET LOCAL statement_timeout = '120s'")
                )

                raw_conn = conn.connection.driver_connection

                with raw_conn.cursor() as cursor:

                    for start in range(
                        0, len(clean_df), LOAD_CHUNK_SIZE
                    ):

                        batch = list(
                            clean_df.iloc[
                                start:start + LOAD_CHUNK_SIZE
                            ].itertuples(index=False, name=None)
                        )

                        execute_values(
                            cursor,
                            insert_query,
                            batch,
                            page_size=1000
                        )

                        loaded_counts[table_name] += len(batch)

                        print(
                            f"  Staged: {loaded_counts[table_name]:,} "
                            f"of {len(clean_df):,} rows"
                        )

            print(
                f"  Successfully staged: {len(df):,} rows"
            )

        # Finalize the last table after all chunks are consumed.
        if active_table_name is not None:
            finalize_table(
                active_table_name,
                staging_table
            )

        return loaded_counts

    finally:
        engine.dispose()
