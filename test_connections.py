
from sqlalchemy import text
from src.db import (
    get_ecom_engine,
    get_saas_engine,
    get_target_engine,
)


connections = {
    "ECOM": get_ecom_engine,
    "SAAS": get_saas_engine,
    "TARGET": get_target_engine,
}

for name, engine_factory in connections.items():
    engine = None

    try:
        engine = engine_factory()

        with engine.connect() as connection:
            result = connection.execute(
                text("""
                    SELECT
                        current_database() AS database_name,
                        current_user AS connected_user,
                        version() AS postgres_version
                """)
            )

            row = result.fetchone()

            print(f"\n{name}: CONNECTION SUCCESSFUL")
            print(f"Database: {row.database_name}")
            print(f"User: {row.connected_user}")
            print(f"Version: {row.postgres_version[:45]}")

    except Exception as error:
        print(f"\n{name}: CONNECTION FAILED")
        print(f"Error: {error}")

    finally:
        if engine is not None:
            engine.dispose()
