
# Tables selected for the raw data landing pipeline.

ECOM_TABLES = [
    "orders",
    "order_items",
    "order_status_history",
    "customers",
    "products",
    "payment_transactions",
    "shipments",
    "sessions",
    "session_events",
    "attribution_touches",
    "devices",
]

SAAS_TABLES = [
    "events",
    "subscriptions",
    "subscription_events",
    "invoices",
    "users",
    "accounts",
]

# Extraction settings
EXTRACTION_CHUNK_SIZE = 10_000
LOAD_CHUNK_SIZE = 1_000


# Logical primary keys used for incremental reconciliation.
# These were validated against the source data.

ECOM_PRIMARY_KEYS = {
    "orders": ["order_id"],
    "order_items": ["order_id", "variant_id"],
    "order_status_history": ["order_id", "status", "changed_at"],
    "customers": ["customer_id"],
    "products": ["product_id"],
    "payment_transactions": ["txn_id"],
    "shipments": ["shipment_id"],
    "sessions": ["session_id"],
    "session_events": ["event_id"],
    "attribution_touches": ["touch_id"],
    "devices": ["device_id"],
}

SAAS_PRIMARY_KEYS = {
    "events": ["event_id"],
    "subscriptions": ["subscription_id"],
    "subscription_events": ["event_id"],
    "invoices": ["invoice_id"],
    "users": ["user_id"],
    "accounts": ["account_id"],
}
