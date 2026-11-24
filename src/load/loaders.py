
from sqlalchemy import Column, MetaData, Table, inspect

from src.config import LOAD_CHUNK_SIZE
from src.db import get_target_engine


def load_chunks(chunks, target_schema, source_engine, source_schema):
    """
    Create raw target tables using source column metadata,
    then insert extracted DataFrame chunks.

    Source column types and nullability are preserved.
    Primary keys, foreign keys, and source defaults are
    intentionally not copied into the raw layer.
    """

    allowed_schemas = {"raw_ecom", "raw_saas"}

    if target_schema not in allowed_schemas:
        raise ValueError(f"Invalid target schema: {target_schema}")

    engine = get_target_engine()
    source_inspector = inspect(source_engine)

    initialized_tables = set()
    target_tables = {}
    loaded_counts = {}

    try:
        for table_name, df in chunks:

            if df is None:
                continue

            if table_name not in initialized_tables:

                print(
                    f"\nPreparing target table: "
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

                target_table = Table(
                    table_name,
                    metadata,
                    *columns,
                    schema=target_schema
                )

                target_table.drop(engine, checkfirst=True)
                target_table.create(engine)

                target_tables[table_name] = target_table
                initialized_tables.add(table_name)
                loaded_counts[table_name] = 0

            if df.empty:
                print("  Empty source table; structure created.")
                continue

            target_table = target_tables[table_name]

            print(
                f"Loading {target_schema}.{table_name}: "
                f"{len(df):,} rows"
            )

            clean_df = df.astype(object).where(df.notna(), None)

            for start in range(0, len(clean_df), LOAD_CHUNK_SIZE):

                batch = clean_df.iloc[
                    start:start + LOAD_CHUNK_SIZE
                ].to_dict(orient="records")

                with engine.begin() as conn:
                    conn.execute(
                        target_table.insert(),
                        batch
                    )

                loaded_counts[table_name] += len(batch)

            print(
                f"  Successfully loaded: "
                f"{len(df):,} rows"
            )

        return loaded_counts

    finally:
        engine.dispose()
