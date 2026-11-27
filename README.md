# Multi-Source Data Engineering Pipeline

## 1. Project Overview

An end-to-end Python data engineering project that integrates data from two PostgreSQL source databases (E-commerce and SaaS) into a centralized PostgreSQL data warehouse hosted on Neon.

The project demonstrates modular ETL development, efficient data extraction, data transformation, warehouse modelling, incremental loading, and data quality monitoring using Python, SQLAlchemy, Pandas, and PostgreSQL.

## 2. Project Objectives

- Connect to multiple PostgreSQL source databases.
- Extract data from E-commerce and SaaS systems efficiently.
- Build a centralized PostgreSQL data warehouse.
- Develop a modular and reusable ETL pipeline.
- Implement data transformations and warehouse modelling.
- Implement data quality checks and pipeline monitoring.
- Handle larger datasets through chunked extraction and batch loading.
- Maintain customer history using Slowly Changing Dimension Type II (SCD Type II).

## 3. Technology Stack

| Technology | Purpose |
|---|---|
| Python 3.13 | ETL pipeline development |
| PostgreSQL | Source databases and target warehouse |
| Neon | Hosted PostgreSQL data warehouse |
| SQLAlchemy | Database connectivity and SQL execution |
| Pandas | Data extraction and transformation |
| psycopg2 | PostgreSQL bulk loading |
| python-dotenv | Environment variable management |
| Git & GitHub | Version control |

## 4. Architecture Overview

### Source Systems

- E-commerce PostgreSQL database
- SaaS PostgreSQL database

### ETL Pipeline

1. Extract source data using keyset pagination.
2. Load source records into raw warehouse schemas using staging tables and batch insertion.
3. Validate source and target row counts.
4. Transform customer records into a consolidated customer dimension.
5. Build fact tables for orders and subscription events.
6. Validate warehouse data quality and referential integrity.

### Target System

Neon PostgreSQL warehouse with three logical schemas:

| Schema | Purpose |
|---|---|
| `raw_ecom` | Raw E-commerce source tables |
| `raw_saas` | Raw SaaS source tables |
| `mart` | Transformed analytical dimension and fact tables |

## 5. Repository Structure

```text
multi-source-data-pipeline/
│
├── scripts/
│   └── check_saas_invoice_loader.py
├── data/
│   └── raw/
├── docs/
│   ├── architecture.md
│   └── target_schema.sql
├── warehouse/
│   └── ddl/
├── src/
│   ├── extract/
│   ├── transform/
│   │   ├── customers.py
│   │   ├── facts.py
│   │   └── saas_facts.py
│   ├── load/
│   ├── db.py
│   ├── monitoring.py
│   └── main.py
├── .env.example
├── .gitignore
├── requirements.txt
└── README.md
├── test_connections.py
```

## 6. Warehouse Data Model

The warehouse contains three analytical tables.

### Dimension Table

**`mart.dim_customer`**

A consolidated customer dimension containing E-commerce customers and SaaS accounts.

- Uses a generated surrogate key (`customer_sk`).
- Identifies source records using `source_system` and `source_customer_id`.
- Maintains historical customer versions using SCD Type II.
- Tracks record validity through `valid_from`, `valid_to`, and `is_current`.

### Fact Tables

**`mart.fact_orders`**

Contains one record per E-commerce order.

- References the customer dimension through `customer_sk`.
- Preserves order-level financial and operational attributes.
- Uses `order_id` as its primary key.

**`mart.fact_subscription_events`**

Contains SaaS subscription lifecycle events.

- References the customer dimension through `customer_sk`.
- Captures subscription changes, event types, plans, MRR changes, and seat changes.
- Uses `event_id` as its primary key.

## 7. Pipeline Implementation

### Data Extraction

- Extracts 11 E-commerce tables and 6 SaaS tables.
- Uses keyset pagination based on source primary keys.
- Supports single-column and composite primary keys.
- Processes records in configurable chunks.

### Raw Data Loading

- Loads records into `raw_ecom` and `raw_saas`.
- Uses staging tables to protect existing target tables during loading.
- Performs batch insertion using `psycopg2.extras.execute_values`.
- Validates row counts before publishing loaded tables.

### Data Transformation

**Customer Dimension**

- Consolidates E-commerce customers and SaaS accounts.
- Standardizes customer attributes.
- Generates surrogate keys.
- Implements incremental SCD Type II processing.

**Order Fact**

- Transforms E-commerce order data.
- Associates orders with historically valid customer dimension records.
- Loads order facts using batch insertion and conflict handling.

**Subscription Event Fact**

- Transforms SaaS subscription events.
- Associates events with historically valid customer dimension records.
- Preserves unmatched events in the raw layer rather than assigning invalid customer keys.

## 8. Setup Instructions

### Prerequisites

- Python 3.13+
- PostgreSQL database access for both source systems
- Neon PostgreSQL target database access
- Git

### Clone the repository

```bash
git clone <repository-url>
cd multi-source-data-pipeline
```

### Create and activate virtual environment

```bash
python -m venv venv
source venv/bin/activate
```

### Install dependencies

```bash
python -m pip install -r requirements.txt
```

### Configure environment variables

Create a `.env` file using `.env.example` as a template.

Configure credentials for:

- E-commerce source database
- SaaS source database
- Neon target warehouse

Configure TARGET_DB_SSLMODE=require for the Neon target warehouse, as specified in .env.example.

Never commit `.env` or database credentials to GitHub.

## 9. Pipeline Execution

### 1. Activate the virtual environment

```bash
source venv/bin/activate
```

### 2. Verify database connections

```bash
python test_connections.py
```

The script checks connectivity to the E-commerce source, SaaS source, and target warehouse.

### 3. Execute the ETL pipeline

From the project root:

```bash
python -m src.main
```

The pipeline currently performs:

1. Extraction of selected E-commerce and SaaS source tables.
2. Loading into raw warehouse schemas using staging tables and batch insertion.
3. Source-to-target row-count validation.
4. Generation of the raw data manifest.
5. Customer dimension transformation and SCD Type II loading.
6. E-commerce order fact transformation and loading.
7. SaaS subscription event fact transformation and loading.

All three transformations are integrated into `src/main.py`. The SaaS subscription event transformation has also been independently executed and validated. However, the complete pipeline has not yet been rerun end-to-end following its final integration.

**Important:** The current `main.py` execution performs a full refresh of the selected raw tables. Do not rerun the entire pipeline merely to retry a downstream transformation.

## 10. Current Warehouse Results

The Neon warehouse has been populated and validated.

### Raw Layer

| Source | Tables | Expected Rows |
|---|---:|---:|
| E-commerce | 11 | 944,414 |
| SaaS | 6 | 67,395 |
| **Total** | **17** | **1,011,809** |

All 17 selected source tables passed source-to-target row-count validation.

### Mart Layer

| Table | Records |
|---|---:|
| `mart.dim_customer` | 11,250 |
| `mart.fact_orders` | 40,000 |
| `mart.fact_subscription_events` | 3,722 |
| **Total** | **54,972** |

### Data Quality Validation

The following checks have been completed:

- Primary-key uniqueness and null checks.
- Foreign-key integrity checks.
- Required-column null checks.
- SCD Type II validity-period checks.
- Current customer record validation.
- Raw source-to-target row-count validation.

All completed checks passed.

Raw-layer validation confirms source-to-target row-count equality. Mart-layer checks cover key uniqueness, referential integrity, required-column nulls, and SCD Type II validity; they do not constitute a full row-by-row comparison against the source systems.

**Documented exception:** 19 SaaS subscription events did not have a historically valid customer dimension match. These events remain available in `raw_saas.subscription_events` and were excluded from `mart.fact_subscription_events`.

## 11. Project Status and Next Steps

### Completed

- Repository setup and environment configuration.
- Multiple PostgreSQL source connections.
- Neon target warehouse configuration.
- Raw data extraction and loading.
- Keyset pagination and batch loading.
- Source-to-target row-count validation.
- Customer dimension modelling and SCD Type II loading.
- E-commerce order fact transformation and loading.
- SaaS subscription event transformation and loading.
- Mart-layer integrity validation.

### Remaining

- Consolidate final validation and monitoring documentation.
- Update architecture and warehouse documentation.
- Complete final code review and Git version control.
- Perform an end-to-end pipeline verification when appropriate.

## 12. Author

Neharika Mandhan