
from numpy import identity, record
import pandas as pd
from sqlalchemy import engine, text

from src.db import get_target_engine

def normalize_missing_values(df):
    """
    Convert Pandas missing values, empty strings,
    and textual missing-value markers to Python None.
    """

    df = df.astype(object)

    df = df.replace(
        r"^\s*$|^(?i:nan)$",
        None,
        regex=True
    )

    return df.where(
        pd.notna(df),
        None
    )


def read_customer_sources():
    """
    Read e-commerce customers and SaaS accounts
    from the raw landing schemas.
    """

    engine = get_target_engine()

    try:
        with engine.connect() as conn:

            ecom_customers = pd.read_sql(
                text("""
                    SELECT *
                    FROM raw_ecom.customers
                """),
                conn
            )

            saas_accounts = pd.read_sql(
                text("""
                    SELECT *
                    FROM raw_saas.accounts
                """),
                conn
            )

    finally:
        engine.dispose()

    return ecom_customers, saas_accounts

def get_first_order_dates():
    """
    Retrieve the earliest observed order timestamp
    for each E-commerce customer.
    """

    engine = get_target_engine()

    try:
        query = text("""
            SELECT
                customer_id,
                MIN(created_at) AS first_order_at
            FROM raw_ecom.orders
            WHERE customer_id IS NOT NULL
            GROUP BY customer_id
        """)

        first_orders = pd.read_sql(query, engine)

        return first_orders

    finally:
        engine.dispose()


def standardize_customer_sources(ecom_customers, saas_accounts):
    """
    Standardize e-commerce customers and SaaS accounts
    into the common dim_customer structure.
    """

    # --- E-commerce customers ---

    first_name = (
        ecom_customers["first_name"]
        .fillna("")
        .astype("string")
        .str.strip()
    )

    last_name = (
        ecom_customers["last_name"]
        .fillna("")
        .astype("string")
        .str.strip()
    )

    customer_name = (
        first_name + " " + last_name
    ).str.strip()

    customer_name = customer_name.replace("", pd.NA)

    # Retrieve each customer's earliest observed order date.
    first_orders = get_first_order_dates()

    # Map the first order date to each customer.
    first_order_map = first_orders.set_index(
    "customer_id"
    )["first_order_at"]

    # Use the first order date when available.
    # Otherwise, fall back to the customer creation date.
    ecom_valid_from = (
    ecom_customers["customer_id"]
    .map(first_order_map)
    .fillna(ecom_customers["created_at"])
)


    ecom_dim = pd.DataFrame({
        "source_system": "ecom",
        "source_customer_id": ecom_customers["customer_id"],
        "customer_name": customer_name,
        "email": ecom_customers["primary_email"],
        "country": ecom_customers["country"],
        "city": ecom_customers["city"],
        "industry": None,
        "employee_count": None,
        "account_type": None,
        "lifecycle_stage": ecom_customers["lifecycle_stage"],
        "acquisition_channel": ecom_customers["acquisition_channel"],
        "valid_from": ecom_valid_from,
        "valid_to": None,
        "is_current": True
    })

    # --- SaaS accounts ---

    saas_dim = pd.DataFrame({
        "source_system": "saas",
        "source_customer_id": saas_accounts["account_id"],
        "customer_name": saas_accounts["name"],
        "email": None,
        "country": saas_accounts["country"],
        "city": None,
        "industry": saas_accounts["industry"],
        "employee_count": saas_accounts["employee_count"],
        "account_type": saas_accounts["account_type"],
        "lifecycle_stage": None,
        "acquisition_channel": saas_accounts["acquisition_channel"],
        "valid_from": saas_accounts["signup_date"],
        "valid_to": None,
        "is_current": True
    })

    # Combine both standardized sources.
    combined_customers = pd.concat(
        [ecom_dim, saas_dim],
        ignore_index=True
    )

    return combined_customers





def load_initial_customers(customers):
    """
    Insert standardized customer records into
    mart.dim_customer when the dimension is empty.
    """

    from sqlalchemy import text

    engine = get_target_engine()
    batch_size = 100

    insert_query = text("""
        INSERT INTO mart.dim_customer (
            source_system,
            source_customer_id,
            customer_name,
            email,
            country,
            city,
            industry,
            employee_count,
            account_type,
            lifecycle_stage,
            acquisition_channel,
            valid_from,
            valid_to,
            is_current
        )
        VALUES (
            :source_system,
            :source_customer_id,
            :customer_name,
            :email,
            :country,
            :city,
            :industry,
            :employee_count,
            :account_type,
            :lifecycle_stage,
            :acquisition_channel,
            :valid_from,
            :valid_to,
            :is_current
        )
    """)

    try:
        with engine.begin() as conn:

            conn.execute(
                text("SET LOCAL statement_timeout = '120s'")
            )

            existing_count = conn.execute(
                text("SELECT COUNT(*) FROM mart.dim_customer")
            ).scalar_one()

            if existing_count > 0:
                raise RuntimeError(
                    "mart.dim_customer is not empty. "
                    "Initial load cannot run."
                )

            customers = normalize_missing_values(customers)
            records = customers.to_dict(orient="records")

            total_records = len(records)

            for start in range(0, total_records, batch_size):

                batch = records[start:start + batch_size]

                conn.execute(insert_query, batch)

                print(
                    f"Inserted {min(start + batch_size, total_records):,}"
                    f" of {total_records:,} records"
                )

        print("\nInitial customer load completed successfully.")

    finally:
        engine.dispose()

def load_incremental_customers(customers):
    """
    Apply incremental SCD Type 2 changes to mart.dim_customer.
    """
    tracked_attributes = {
        "ecom": [
            "customer_name",
            "email",
            "country",
            "city",
            "lifecycle_stage",
            "acquisition_channel"
        ],
        "saas": [
            "customer_name",
            "country",
            "industry",
            "employee_count",
            "account_type"
        ]
    }

    engine = get_target_engine()
    
    
    try:
        with engine.begin() as conn:

            conn.execute(
                text("SET LOCAL statement_timeout = '120s'")
            )
    
            observation_time = conn.execute(
                text("SELECT CURRENT_TIMESTAMP")
            ).scalar_one()
            current_customers = pd.read_sql(
                text("""
                    SELECT
                        source_system,
                        source_customer_id,
                        customer_name,
                        email,
                        country,
                        city,
                        industry,
                        employee_count,
                        account_type,
                        lifecycle_stage,
                        acquisition_channel
                    FROM mart.dim_customer
                    WHERE is_current = TRUE
                    FOR UPDATE
                """),
                conn
            )
            # Normalize missing values before comparison.
            customers = normalize_missing_values(customers)
            current_customers = normalize_missing_values(
                current_customers
            )

            # Build a lookup using source identity.
            current_lookup = {
                (record["source_system"], record["source_customer_id"]): record
                for record in current_customers.to_dict(orient="records")
            }

            # Convert incoming customer data into records.
            incoming_records = customers.to_dict(orient="records")
                        # Prepare lists for each type of customer record.
            new_records = []
            changed_records = []
            unchanged_count = 0

            # Compare incoming records with current dimension records.
            for incoming in incoming_records:

                identity = (
                    incoming["source_system"],
                    incoming["source_customer_id"]
                )

                current = current_lookup.get(identity)

                # Case 1: New customer.
                if current is None:
                    new_records.append(incoming)
                    continue

                # Check whether any tracked attribute has changed.
                has_changes = any(
            not (
                pd.isna(incoming[attribute])
                and pd.isna(current[attribute])
            )
            and (
                pd.isna(incoming[attribute])
                or pd.isna(current[attribute])
                or incoming[attribute] != current[attribute]
            )
            for attribute in tracked_attributes[
                incoming["source_system"]
            ]
        )

                # Case 2: Existing customer with changes.
                if has_changes:
                    changed_records.append(incoming)

                # Case 3: Existing customer without changes.
                else:
                    unchanged_count += 1
                # Expire the existing versions of changed customers.
            for record in changed_records:

                conn.execute(
                    text("""
                        UPDATE mart.dim_customer
                        SET
                            valid_to = :valid_to,
                            is_current = FALSE
                        WHERE source_system = :source_system
                          AND source_customer_id = :source_customer_id
                          AND is_current = TRUE
                    """),
                    {
                        "valid_to": observation_time,
                        "source_system": record["source_system"],
                        "source_customer_id": record["source_customer_id"]
                    }
                )
                # Combine new customers and changed customer versions.
            records_to_insert = new_records + changed_records

            # Insert new current versions.
            if records_to_insert:

                insert_query = text("""
                    INSERT INTO mart.dim_customer (
                        source_system,
                        source_customer_id,
                        customer_name,
                        email,
                        country,
                        city,
                        industry,
                        employee_count,
                        account_type,
                        lifecycle_stage,
                        acquisition_channel,
                        valid_from,
                        valid_to,
                        is_current
                    )
                    VALUES (
                        :source_system,
                        :source_customer_id,
                        :customer_name,
                        :email,
                        :country,
                        :city,
                        :industry,
                        :employee_count,
                        :account_type,
                        :lifecycle_stage,
                        :acquisition_channel,
                        :valid_from,
                        NULL,
                        TRUE
                    )
                """)

                for record in records_to_insert:

                    identity = (
                        record["source_system"],
                        record["source_customer_id"]
                )

                    if identity in current_lookup or record["valid_from"] is None:
                        record["valid_from"] = observation_time

                conn.execute(insert_query, records_to_insert)
            print("\nIncremental customer load completed successfully.")
            print(f"New customers inserted: {len(new_records):,}")
            print(f"Changed customers: {len(changed_records):,}")
            print(f"Unchanged customers: {unchanged_count:,}")
            print(f"Total records inserted: {len(records_to_insert):,}")
    finally:
        engine.dispose()