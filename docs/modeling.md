# Data Warehouse Modeling Specification

## 1. Overview

This document defines the analytical serving layer for the multi-source data pipeline. The warehouse integrates e-commerce data from the `ecom` source schema and SaaS data from the `saas` source schema into a shared dimensional model.

The serving layer consists of three tables:

- `dim_customer`: A shared customer dimension using Slowly Changing Dimension Type II (SCD Type II).
- `fact_orders`: An e-commerce order fact table.
- `fact_subscription_events`: A SaaS subscription event fact table.

The model follows a star-schema approach. Both fact tables reference the shared customer dimension through a warehouse-generated surrogate key.

## 2. Dimension Design: dim_customer

### Purpose

`dim_customer` provides a consistent customer reference across the e-commerce and SaaS datasets.

It combines:
- Individual customers from `ecom.customers`.
- Business and self-serve accounts from `saas.accounts`.

The `source_system` column distinguishes the originating system, while `source_customer_id` preserves the original customer or account identifier.

SaaS users are not treated as separate customer-dimension records in this model. User identifiers are retained in the subscription event fact table where relevant.

### Grain

**One row per source customer identity per version of its tracked attributes.**

A customer can therefore have multiple dimension rows over time, but only one current version.

### Key attributes

| Column | Description |
|---|---|
| customer_sk | Warehouse-generated surrogate primary key |
| source_system | Source identifier: `ecom` or `saas` |
| source_customer_id | Original customer ID or account ID |
| customer_name | Standardized customer or account name |
| country, city | Location attributes where available |
| industry | SaaS account industry where available |
| employee_count | SaaS account employee count where available |
| account_type | SaaS account classification where available |
| lifecycle_stage | E-commerce customer lifecycle stage where available |
| acquisition_channel | Acquisition channel where available |
| valid_from | Timestamp when this dimension version becomes valid |
| valid_to | Timestamp when this dimension version expires |
| is_current | Indicates whether this is the current version |

Attributes that do not exist in a particular source will be nullable.

### SCD Type II Strategy

SCD Type II preserves historical changes to tracked customer attributes.

The implementation follows these rules:

1. If a source customer or account does not exist in the dimension, insert a new record.
2. If tracked attributes change, expire the existing record and insert a new version.
3. If tracked attributes have not changed, retain the existing record without creating another version.
4. Preserve previous versions for historical reporting.

### Tracked Attributes

Changes to the following attributes will trigger a new SCD Type II dimension version:

**Common attributes**
- `customer_name`
- `country`

**E-commerce customer attributes**
- `email`
- `city`
- `lifecycle_stage`
- `acquisition_channel`

**SaaS account attributes**
- `industry`
- `employee_count`
- `account_type`

Only attributes available in the respective source system are evaluated. A change to any tracked attribute expires the existing dimension record and creates a new version. Unchanged attributes do not create additional versions.

### Initial Validity and Change Detection Timestamps

For the initial dimension record, `valid_from` will use the source entity's creation or signup timestamp where available:

- E-commerce customers: `ecom.customers.created_at`.
- SaaS accounts: `saas.accounts.signup_date`.

If the source timestamp is missing, the pipeline's initial observation timestamp will be used as a fallback.

For subsequent attribute changes, the new dimension version's `valid_from` will use the timestamp at which the pipeline detects the change. The previous version will be expired at the same timestamp by setting its `valid_to` value.

This approach preserves the earliest available source date for initial records while maintaining consistent version boundaries for changes observed by the pipeline.

### SaaS Event Timestamp Handling

The source column `saas.subscription_events.event_time` is defined as `TIMESTAMP WITHOUT TIME ZONE`.

Inspection of all 3,741 non-null event timestamps confirmed that every value occurs at midnight (`00:00:00`). This indicates that the source currently represents events with date-level timestamp values.

The warehouse preserves this column as `TIMESTAMP WITHOUT TIME ZONE` in `fact_subscription_events`, without assigning an assumed timezone.

The SaaS account `signup_date` column is `TIMESTAMP WITH TIME ZONE`, and sampled values explicitly include the UTC offset (`+00`).

Because the event timestamps do not contain timezone information, their timezone interpretation must be established before comparing them with the timezone-aware SCD Type II validity columns. No implicit timezone conversion will be applied.


The validity interval is defined as `valid_from` inclusive and `valid_to` exclusive. Current records will have `is_current = TRUE` and `valid_to IS NULL`.

The combination of `source_system` and `source_customer_id` identifies a source entity across its historical versions. A surrogate key identifies each individual dimension version.

**Historical limitation:** Raw source tables are refreshed during extraction. Consequently, SCD Type II can preserve changes observed between pipeline runs, but cannot reconstruct intermediate changes that occurred between snapshots.

## 3. Fact Design: fact_orders

### Purpose

`fact_orders` stores e-commerce order-level measures and connects each order to the appropriate customer dimension version.

### Grain

**One row per unique e-commerce order, identified by `order_id`.**

### Source

- `raw_ecom.orders`
- `dim_customer`

### Key fields and measures

| Column | Description |
|---|---|
| order_id | Source order identifier and fact-table business key |
| customer_sk | Foreign key to the applicable customer dimension version |
| created_at | Order creation timestamp |
| status | Order status |
| payment_status | Payment status |
| subtotal | Order subtotal |
| discount | Order discount |
| tax | Order tax |
| shipping_fee | Shipping fee |
| total | Final order total |

The customer surrogate key should identify the dimension version valid at the order's `created_at` timestamp.

This fact table has an order-level grain. Individual products and quantities within an order are not represented at line-item level. Product-level analysis would require a separate order-item fact table, which is outside the current milestone scope.

## 4. Fact Design: fact_subscription_events

### Purpose

`fact_subscription_events` stores SaaS subscription lifecycle events and supports analysis of subscription changes over time.

### Grain

**One row per unique SaaS subscription event, identified by `event_id`.**

### Source

- `raw_saas.subscription_events`
- `dim_customer`

### Key fields and measures

| Column | Description |
|---|---|
| event_id | Source subscription event identifier and fact-table business key |
| customer_sk | Foreign key to the SaaS account's dimension record |
| subscription_id | Source subscription identifier |
| user_id | User associated with the event, where available |
| actor_user_id | User who performed the event, where available |
| event_type | Type of subscription event |
| event_time | Timestamp when the event occurred |
| from_plan | Previous subscription plan |
| to_plan | New subscription plan |
| mrr_delta | Change in monthly recurring revenue |
| seats_delta | Change in subscription seats |

The customer surrogate key links the event to the corresponding SaaS account in `dim_customer`. User identifiers remain source-system references rather than customer-dimension foreign keys.

## 5. Relationships and Data Integrity

The model uses the following relationships:

- `fact_orders.customer_sk` references `dim_customer.customer_sk`.
- `fact_subscription_events.customer_sk` references `dim_customer.customer_sk`.

The source relationships between orders and customers, and between subscription events and accounts, have been validated against the source data. These relationships are logical data relationships even where the source database does not declare foreign-key constraints.

Before loading the analytical tables, transformations must validate:

- Primary-key uniqueness.
- Required-field non-null constraints.
- Foreign-key integrity.
- Valid dimension-version lookups.
- Expected source-to-target row counts.
- SCD Type II current-record uniqueness.

A failed critical validation must prevent the affected mart load.

## 6. Partitioning, Indexing and Cost Rationale

The current datasets contain approximately 40,000 e-commerce orders and 3,741 SaaS subscription events. At this scale, partitioning would add operational complexity without a clear performance benefit.

The initial design will therefore avoid partitioning.

| Table | Initial physical design | Rationale |
|---|---|---|
| dim_customer | Index on source identity; unique index for current source records | Supports source lookups and SCD processing |
| fact_orders | Indexes on customer_sk and created_at | Supports customer-level and time-based queries |
| fact_subscription_events | Indexes on customer_sk and event_time | Supports account-level and event-time analysis |

If fact-table volumes grow substantially, range partitioning by `created_at` for orders and `event_time` for subscription events can be evaluated, potentially using monthly partitions.

PostgreSQL does not provide BigQuery-style continuously maintained clustering keys. This design uses indexes for query access paths. PostgreSQL's `CLUSTER` command can physically reorder a table using an index, but that ordering is not automatically maintained after subsequent writes.

Avoiding unnecessary partitions and indexes keeps storage, maintenance, and query-planning overhead proportionate to the current data volume.

## 7. Implementation and Verification

The serving layer will be implemented in the following order:

1. Create the three mart tables using commented PostgreSQL DDL.
2. Execute the DDL in the target PostgreSQL warehouse and verify that the tables, constraints, and indexes are created successfully.
3. Implement dimension and fact transformations in `src/transform/`.
4. Validate transformed data before loading.
5. Load the analytical tables and verify keys, relationships, and row counts.

The final model will provide a consistent customer dimension, order-level e-commerce analytics, and subscription-event analytics while retaining historical customer information through SCD Type II.