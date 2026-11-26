import pandas as pd
from psycopg2.extras import execute_values
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

        orders = pd.read_sql(
            query,
            engine,
            coerce_float=False
        )

        print(f"Orders extracted: {len(orders):,}")

        return orders

    finally:
        engine.dispose()



def read_customer_dimension():
    """
    Read the customer dimension from the mart schema.
    """

    engine = get_target_engine()

    try:
        query = text("""
            SELECT
                customer_sk,
                source_system,
                source_customer_id,
                valid_from,
                valid_to
            FROM mart.dim_customer
            WHERE source_system = 'ecom'
        """)

        customers = pd.read_sql(query, engine)

        print(
            f"E-commerce customer dimension records extracted: "
            f"{len(customers):,}"
        )

        return customers

    finally:
        engine.dispose()


def attach_customer_keys(orders, customers):
    """
    Attach the correct customer surrogate key to each order
    using the dimension's SCD Type II validity period.
    """

    # Keep only the columns required for the lookup.
    customer_lookup = customers[
        [
            "source_customer_id",
            "customer_sk",
            "valid_from",
            "valid_to"
        ]
    ].copy()

    # Normalize timestamps to UTC for consistent comparison.
    orders = orders.copy()

    orders["created_at"] = pd.to_datetime(
        orders["created_at"],
        utc=True
    )

    customer_lookup["valid_from"] = pd.to_datetime(
        customer_lookup["valid_from"],
        utc=True
    )

    customer_lookup["valid_to"] = pd.to_datetime(
        customer_lookup["valid_to"],
        utc=True
    )

    # Match orders to customer identities.
    candidates = orders[
        ["order_id", "customer_id", "created_at"]
    ].merge(
        customer_lookup,
        left_on="customer_id",
        right_on="source_customer_id",
        how="left"
    )

    # Keep only the dimension version valid at order time.
    valid_matches = candidates[
        candidates["customer_sk"].notna()
        & (candidates["created_at"] >= candidates["valid_from"])
        & (
            candidates["valid_to"].isna()
            | (candidates["created_at"] < candidates["valid_to"])
        )
    ].copy()

    # Check whether an order matched multiple dimension versions.
    match_counts = valid_matches.groupby("order_id").size()

    duplicate_matches = match_counts[match_counts > 1]

    if not duplicate_matches.empty:
        raise ValueError(
            f"{len(duplicate_matches)} orders matched multiple "
            "customer dimension versions."
        )

    # Attach the matched surrogate keys to the original orders.
    order_keys = valid_matches[
        ["order_id", "customer_sk"]
    ]

    orders = orders.merge(
        order_keys,
        on="order_id",
        how="left",
        validate="one_to_one"
    )

    matched_orders = orders["customer_sk"].notna().sum()
    unmatched_orders = orders["customer_sk"].isna().sum()

    print(f"Orders with customer keys: {matched_orders:,}")
    print(f"Orders without customer keys: {unmatched_orders:,}")

    return orders


def prepare_orders():
    """
    Extract orders and customer dimension records,
    then attach customer surrogate keys.
    """

    orders = read_orders()
    customers = read_customer_dimension()

    orders = attach_customer_keys(orders, customers)

    print("\nOrder transformation summary:")
    print(f"Total orders: {len(orders):,}")
    print(f"Unique order IDs: {orders['order_id'].nunique():,}")
    print(
        f"Matched orders: "
        f"{orders['customer_sk'].notna().sum():,}"
    )

    return orders


def select_fact_order_columns(orders):
    """
    Select and arrange columns required by mart.fact_orders.
    """

    fact_orders = orders[
        [
            "order_id",
            "customer_sk",
            "created_at",
            "status",
            "payment_status",
            "subtotal",
            "discount",
            "tax",
            "shipping_fee",
            "total"
        ]
    ].copy()

    print("\nFact orders prepared:")
    print(f"Rows: {len(fact_orders):,}")
    print(f"Columns: {list(fact_orders.columns)}")

    return fact_orders



def load_fact_orders(fact_orders, batch_size=1000):
    """
    Load transformed orders into mart.fact_orders
    using Psycopg2 bulk inserts within one transaction.
    """
    engine = get_target_engine()

    insert_query = """
        INSERT INTO mart.fact_orders (
            order_id,
            customer_sk,
            created_at,
            status,
            payment_status,
            subtotal,
            discount,
            tax,
            shipping_fee,
            total
        )
        VALUES %s
    """

    insert_template = """
        (
            %(order_id)s,
            %(customer_sk)s,
            %(created_at)s,
            %(status)s,
            %(payment_status)s,
            %(subtotal)s,
            %(discount)s,
            %(tax)s,
            %(shipping_fee)s,
            %(total)s
        )
    """

    try:
        records = fact_orders.to_dict(orient="records")
        total_records = len(records)

        with engine.begin() as conn:
            conn.execute(
                text("SET LOCAL statement_timeout = '120s'")
            )

            raw_conn = conn.connection.driver_connection

            with raw_conn.cursor() as cursor:
                for start in range(0, total_records, batch_size):
                    batch = records[start:start + batch_size]
                    batch_number = (start // batch_size) + 1

                    print(
                        f"Starting batch {batch_number}: "
                        f"{len(batch):,} records",
                        flush=True
                    )

                    execute_values(
                        cursor,
                        insert_query,
                        batch,
                        template=insert_template,
                        page_size=batch_size
                    )

                    inserted = min(start + batch_size, total_records)

                    print(
                        f"Completed: {inserted:,} "
                        f"of {total_records:,} orders",
                        flush=True
                    )

        print("\nFact orders loaded successfully.")

    finally:
        engine.dispose()
