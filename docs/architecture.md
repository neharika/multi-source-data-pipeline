# Data Pipeline Architecture

## 1. Overview

This project implements a multi-source data engineering pipeline that integrates data from two PostgreSQL source schemas into a centralized PostgreSQL warehouse hosted on Supabase.

The pipeline is developed using Python and SQLAlchemy, with a modular architecture that separates database connectivity, extraction, transformation, loading, and monitoring.

## 2. Source Systems

The pipeline uses two read-only source schemas hosted in the same PostgreSQL database.

| Source | Database | Schema | Access |
|---|---|---|---|
| E-commerce | neondb | ecom | Read-only |
| SaaS | neondb | saas | Read-only |

Both source systems are accessed independently using their respective database credentials.

## 3. Target Warehouse

| Component | Configuration |
|---|---|
| Platform | Supabase |
| Database | postgres |
| Schema | To be defined |
| Access | Write-enabled |
| Connection | PostgreSQL via SQLAlchemy |
| SSL | Certificate verification |

The target warehouse provides a centralized destination for data extracted from both source systems.

Target schemas and raw landing tables will be defined during warehouse implementation.

## 4. High-Level Architecture

```text
       SOURCE SYSTEMS
              
   E-commerce       SaaS
   PostgreSQL      PostgreSQL
   (ecom)           (saas)
       |                |
       |                |
       v                v
   +------------------------+
   |     Python ETL         |
   |                        |
   |  1. Extraction         |
   |  2. Transformation     |
   |  3. Loading            |
   |  4. Monitoring         |
   +------------------------+
                |
                v
       TARGET WAREHOUSE
          Supabase
         PostgreSQL
                |
                v
          Data Storage
```

## 5. Pipeline Components

### 5.1 Database Connectivity — src/db.py

- Establishes connections to the E-commerce source.
- Establishes connections to the SaaS source.
- Establishes a connection to the target warehouse.
- Loads database credentials through environment variables.
- Configures secure database connections.

### 5.2 Extraction — src/extract/

Responsible for extracting data independently from the two source systems.

- ecom_extract.py — E-commerce data extraction.
- saas_extract.py — SaaS data extraction.

### 5.3 Transformation — src/transform/

Responsible for data transformation and preparation before loading.

- customers.py — Customer-related transformations.
- facts.py — Fact-related transformations.

### 5.4 Loading — src/load/

Responsible for loading processed data into the target warehouse.

- loaders.py — Data loading operations.

### 5.5 Monitoring — src/monitoring.py

Responsible for monitoring pipeline execution and data quality.

### 5.6 Orchestration — src/main.py

Coordinates the execution of the pipeline components.

## 6. Configuration and Security

Database credentials are managed through environment variables using a local `.env` file.

Security practices include:

- Source databases