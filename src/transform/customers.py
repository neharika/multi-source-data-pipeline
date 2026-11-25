
import pandas as pd
from sqlalchemy import text

from src.db import get_target_engine


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
        "valid_from": ecom_customers["created_at"],
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

