# Multi-Source Data Engineering Pipeline

## 1. Project Overview

An end-to-end Python data engineering project that integrates data from two PostgreSQL source databases (E-commerce and SaaS) into a centralized PostgreSQL data warehouse.

The project demonstrates data extraction, transformation, loading (ETL), database management, and data quality monitoring using Python and SQLAlchemy.

## 2. Project Objectives

- Connect to multiple PostgreSQL source databases.
- Extract data from E-commerce and SaaS systems.
- Build a centralized PostgreSQL warehouse.
- Develop a modular and reusable ETL pipeline.
- Implement data quality checks and pipeline monitoring.
- Handle larger datasets efficiently.

## 3. Technology Stack

| Technology | Purpose |
|---|---|
| Python 3.13 | Pipeline development |
| PostgreSQL | Source databases and target warehouse |
| SQLAlchemy | Database connectivity |
| Pandas | Data processing |
| psycopg2 | PostgreSQL connectivity |
| python-dotenv | Environment variable management |
| Supabase | Hosted PostgreSQL warehouse |
| Git & GitHub | Version control |

## 4. Architecture Overview

**Source Systems**

- E-commerce PostgreSQL database
- SaaS PostgreSQL database

**ETL Pipeline**

- Extract data from source databases.
- Transform data as required.
- Load data into the target warehouse.
- Monitor pipeline execution and data quality.

**Target System**

- Supabase PostgreSQL warehouse.

## 5. Repository Structure

```text
multi-source-data-pipeline/
│
├── certs/
├── data/
│   └── raw/
├── docs/
│   ├── architecture.md
│   └── target_schema.sql
├── src/
│   ├── extract/
│   ├── transform/
│   ├── load/
│   ├── db.py
│   ├── monitoring.py
│   └── main.py
├── .env.example
├── .gitignore
├── requirements.txt
└── README.md
```

## 6. Setup Instructions

### Prerequisites

- Python 3.10 or higher
- PostgreSQL database access
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

Add the credentials for:
- E-commerce source database
- SaaS source database
- Target PostgreSQL warehouse

Never commit `.env` or database credentials to GitHub.

## 7. Pipeline Execution

### Prerequisites

- Python 3.13+
- PostgreSQL source database access for E-commerce and SaaS
- Supabase PostgreSQL target database access
- Environment variables configured in `.env`
- Target SSL certificate available at the configured path

### 1. Activate the Virtual Environment

From the project root:

```bash
source venv/bin/activate
```

### 2. Verify Database Connections

Run:

```bash
python test_connections.py
```

The script checks connectivity to all three databases:
- E-commerce source
- SaaS source
- Target warehouse

### 3. Run the Loader Test

Run:

```bash
python test_loader.py
```

This tests staging-table creation, data insertion, row-count verification, table publication, and column-type preservation using sample records.

### 4. Execute the ETL Pipeline

Run the pipeline from the project root:

```bash
python -m src.main
```

The pipeline performs the following operations:

1. Extracts the selected E-commerce and SaaS source tables in chunks.
2. Creates staging tables in the target warehouse.
3. Loads extracted records in batches.
4. Verifies staging row counts before publishing target tables.
5. Compares source and target row counts.
6. Generates `data/raw/MANIFEST.md` with table-level validation results.

### 5. Expected Validation Results

The current pipeline is configured to process 17 selected tables:

| Source | Tables | Expected Rows |
|---|---:|---:|
| E-commerce | 11 | 944,414 |
| SaaS | 6 | 67,395 |
| **Total** | **17** | **1,011,809** |

A successful execution should report:

- 17 tables validated
- 17 passed
- 0 failed
- All source and target row counts match

The generated manifest is saved at:

`data/raw/MANIFEST.md`

**Note:** The pipeline performs a full refresh of the selected target tables. Existing target tables are replaced only after their corresponding staging tables have been loaded and verified. Source databases are read-only and are not modified.


## 8. Project Status

**Current milestone:** Milestone 1 — Repository Setup, Warehouse Configuration and Raw Data Landing.

## 9. Future Development

- Data transformation
- Warehouse modelling
- Data quality validation
- Pipeline monitoring

## 10. Author

Neharika Mandhan