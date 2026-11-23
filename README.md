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

Execution instructions will be added as the ETL pipeline is developed.

## 8. Project Status

**Current milestone:** Milestone 1 — Repository Setup, Warehouse Configuration and Raw Data Landing.

## 9. Future Development

- Source data extraction
- Raw data ingestion
- Data transformation
- Warehouse modelling
- Data quality validation
- Pipeline monitoring

## 10. Author

Neharika Mandhan