
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
LOAD_CHUNK_SIZE = 5_000
