import pandas as pd
from psycopg2.extras import execute_values
from sqlalchemy import text

from src.db import get_target_engine


def read_subscription_events():
    """
    Read subscription events from the raw SaaS schema.
    """

    engine = get_target_engine()

    try:
        query = text("""
            SELECT *
            FROM raw_saas.subscription_events
        """)

        events = pd.read_sql(
            query,
            engine,
            coerce_float=False
        )

        print(f"Subscription events extracted: {len(events):,}")

        return events

    finally:
        engine.dispose()


def read_saas_customer_dimension():
    """
    Read SaaS customer dimension records.
    """

    engine = get_target_engine()

    try:
        query = text("""
            SELECT
                customer_sk,
                source_customer_id,
                valid_from,
                valid_to
            FROM mart.dim_customer
            WHERE source_system = 'saas'
        """)

        customers = pd.read_sql(query, engine)

        print(
            "SaaS customer dimension records extracted: "
            f"{len(customers):,}"
        )

        return customers

    finally:
        engine.dispose()


def attach_customer_keys(events, customers):
    """
    Attach customer surrogate keys using SCD Type II
    validity periods and account IDs.
    """

    customer_lookup = customers[
        [
            "source_customer_id",
            "customer_sk",
            "valid_from",
            "valid_to"
        ]
    ].copy()

    events = events.copy()

    # Normalize timestamps for consistent comparison.
    events["event_time"] = pd.to_datetime(
        events["event_time"],
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

    # Match events to customer identities.
    candidates = events[
        ["event_id", "account_id", "event_time"]
    ].merge(
        customer_lookup,
        left_on="account_id",
        right_on="source_customer_id",
        how="left"
    )

    # Retain only dimension versions valid at event time.
    valid_matches = candidates[
        candidates["customer_sk"].notna()
        & (candidates["event_time"] >= candidates["valid_from"])
        & (
            candidates["valid_to"].isna()
            | (candidates["event_time"] < candidates["valid_to"])
        )
    ].copy()

    # Ensure each event matches at most one dimension version.
    match_counts = valid_matches.groupby("event_id").size()

    duplicate_matches = match_counts[match_counts > 1]

    if not duplicate_matches.empty:
        raise ValueError(
            f"{len(duplicate_matches)} events matched multiple "
            "customer dimension versions."
        )

    # Attach valid surrogate keys.
    event_keys = valid_matches[
        ["event_id", "customer_sk"]
    ]

    events = events.merge(
        event_keys,
        on="event_id",
        how="left",
        validate="one_to_one"
    )

    matched_events = events["customer_sk"].notna().sum()
    unmatched_events = events["customer_sk"].isna().sum()

    print(f"Events with customer keys: {matched_events:,}")
    print(f"Events without customer keys: {unmatched_events:,}")

    if matched_events + unmatched_events != len(events):
        raise ValueError("Customer-key matching count validation failed.")

    return events


def prepare_subscription_events():
    """
    Extract subscription events and customer dimension records,
    then attach historical customer surrogate keys.
    """

    events = read_subscription_events()
    customers = read_saas_customer_dimension()

    events = attach_customer_keys(events, customers)

    print("\nSubscription event transformation summary:")
    print(f"Total events: {len(events):,}")
    print(
        f"Matched events: "
        f"{events['customer_sk'].notna().sum():,}"
    )
    print(
        f"Unmatched events: "
        f"{events['customer_sk'].isna().sum():,}"
    )

    return events


def select_fact_subscription_event_columns(events):
    """
    Select columns required by mart.fact_subscription_events.
    Exclude events without a historically valid customer key.
    """

    fact_events = events[
        events["customer_sk"].notna()
    ].copy()

    fact_events = fact_events[
        [
            "event_id",
            "customer_sk",
            "subscription_id",
            "user_id",
            "actor_user_id",
            "event_type",
            "event_time",
            "from_plan",
            "to_plan",
            "mrr_delta",
            "seats_delta"
        ]
    ].copy()

    # Target event_time is TIMESTAMP WITHOUT TIME ZONE.
    # Store the UTC timestamp without its timezone marker.

    fact_events["event_time"] = (
        pd.to_datetime(fact_events["event_time"], utc=True)
        .dt.tz_localize(None)
    )

    fact_events["customer_sk"] = (
        fact_events["customer_sk"].astype("int64")
    )

    print("\nFact subscription events prepared:")
    print(f"Rows: {len(fact_events):,}")
    print(f"Columns: {list(fact_events.columns)}")

    return fact_events


def load_fact_subscription_events(fact_events, batch_size=1000):
    """
    Load transformed subscription events into
    mart.fact_subscription_events using batched upserts.
    """

    if batch_size <= 0:
        raise ValueError("batch_size must be greater than zero.")

    engine = get_target_engine()

    insert_query = """
        INSERT INTO mart.fact_subscription_events (
            event_id,
            customer_sk,
            subscription_id,
            user_id,
            actor_user_id,
            event_type,
            event_time,
            from_plan,
            to_plan,
            mrr_delta,
            seats_delta
        )
        VALUES %s
        ON CONFLICT (event_id)
        DO UPDATE SET
            customer_sk = EXCLUDED.customer_sk,
            subscription_id = EXCLUDED.subscription_id,
            user_id = EXCLUDED.user_id,
            actor_user_id = EXCLUDED.actor_user_id,
            event_type = EXCLUDED.event_type,
            event_time = EXCLUDED.event_time,
            from_plan = EXCLUDED.from_plan,
            to_plan = EXCLUDED.to_plan,
            mrr_delta = EXCLUDED.mrr_delta,
            seats_delta = EXCLUDED.seats_delta
        WHERE (
            mart.fact_subscription_events.customer_sk,
            mart.fact_subscription_events.subscription_id,
            mart.fact_subscription_events.user_id,
            mart.fact_subscription_events.actor_user_id,
            mart.fact_subscription_events.event_type,
            mart.fact_subscription_events.event_time,
            mart.fact_subscription_events.from_plan,
            mart.fact_subscription_events.to_plan,
            mart.fact_subscription_events.mrr_delta,
            mart.fact_subscription_events.seats_delta
        ) IS DISTINCT FROM (
            EXCLUDED.customer_sk,
            EXCLUDED.subscription_id,
            EXCLUDED.user_id,
            EXCLUDED.actor_user_id,
            EXCLUDED.event_type,
            EXCLUDED.event_time,
            EXCLUDED.from_plan,
            EXCLUDED.to_plan,
            EXCLUDED.mrr_delta,
            EXCLUDED.seats_delta
        )
    """

    insert_template = """
        (
            %(event_id)s,
            %(customer_sk)s,
            %(subscription_id)s,
            %(user_id)s,
            %(actor_user_id)s,
            %(event_type)s,
            %(event_time)s,
            %(from_plan)s,
            %(to_plan)s,
            %(mrr_delta)s,
            %(seats_delta)s
        )
    """

    try:
        # Convert pandas missing values (NaN/NaT) to Python None
        # so PostgreSQL receives SQL NULL.
        clean_events = fact_events.astype(object).where(
            pd.notna(fact_events),
            None
        )

        records = clean_events.to_dict(orient="records")
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
                        f"of {total_records:,} subscription events",
                        flush=True
                    )

        print("\nFact subscription events loaded successfully.")

    finally:
        engine.dispose()