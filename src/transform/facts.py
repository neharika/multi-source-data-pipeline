import pandas as pd
from sqlalchemy import text

from src.db import get_target_engine

def read_orders():
    """
    Read orders from the raw E-commerce schema.
    """

    engine = get_target_engine()

    try:
        query = text("""
            SELECT *
            FROM raw_ecom.orders
        """)

        orders = pd.read_sql(query, engine)

        print(f"Orders extracted: {len(orders):,}")

        return orders

    finally:
        engine.dispose()