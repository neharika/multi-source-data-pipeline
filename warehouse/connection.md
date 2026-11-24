# Warehouse Connection Documentation

## 1. Overview

The target data warehouse for the Multi-Source Data Pipeline project is **Supabase PostgreSQL**.

The pipeline connects to two independent PostgreSQL source databases:

- E-commerce source database
- SaaS source database

Data is extracted from the source databases using read-only credentials and loaded into dedicated raw landing schemas in the target warehouse.

## 2. Database Configuration

| Component | Platform | Database | Schema |
|---|---|---|---|
| E-commerce Source | PostgreSQL | Source database | `ecom` |
| SaaS Source | PostgreSQL | Source database | `saas` |
| Target Warehouse | Supabase PostgreSQL | `postgres` | `raw_ecom`, `raw_saas` |

## 3. Target Schema Layout

Two schemas have been created in the target warehouse:

### `raw_ecom`

Raw landing area for data extracted from the E-commerce source database.

### `raw_saas`

Raw landing area for data extracted from the SaaS source database.

These schemas separate source data and preserve the original source-system structure before downstream transformation.

## 4. Database Roles and Permissions

The pipeline uses separate database credentials for each connection.

| Connection | Access Level | Purpose |
|---|---|---|
| E-commerce Source | Read-only | Extract source data |
| SaaS Source | Read-only | Extract source data |
| Target Warehouse | Write access | Create and populate raw landing tables |

Source database credentials are configured independently from target warehouse credentials.

The target database account must have the necessary permissions to create tables and insert data into `raw_ecom` and `raw_saas`.

Actual PostgreSQL role names and grants are managed in the respective database environments.

## 5. Environment Variables

Database credentials are managed through environment variables stored in the project-root `.env` file.

The `.env.example` file provides the configuration template.

Required variables:

**E-commerce Source**
- `ECOM_DB_USER`
- `ECOM_DB_PASS`
- `ECOM_DB_HOST`
- `ECOM_DB_PORT`
- `ECOM_DB_NAME`
- `ECOM_DB_SCHEMA`

**SaaS Source**
- `SAAS_DB_USER`
- `SAAS_DB_PASS`
- `SAAS_DB_HOST`
- `SAAS_DB_PORT`
- `SAAS_DB_NAME`
- `SAAS_DB_SCHEMA`

**Target Warehouse**
- `TARGET_DB_USER`
- `TARGET_DB_PASS`
- `TARGET_DB_HOST`
- `TARGET_DB_PORT`
- `TARGET_DB_NAME`
- `TARGET_DB_SSLMODE`
- `TARGET_DB_SSLROOTCERT`

Credentials must never be committed to version control.

## 6. Connection Implementation

Database connections are implemented in `src/db.py` using:

- SQLAlchemy for database engine creation.
- python-dotenv for loading environment variables.
- psycopg2 as the PostgreSQL database driver.

The following functions provide independent database connections:

| Function | Connection |
|---|---|
| `get_ecom_engine()` | E-commerce source |
| `get_saas_engine()` | SaaS source |
| `get_target_engine()` | Supabase target warehouse |

Connection engines use `pool_pre_ping=True` to check connection availability before using pooled connections.

## 7. SSL Configuration

SSL is enabled for all database connections.

**Source databases:**

- SSL mode: `require`

**Target warehouse:**

- SSL mode: `verify-full`
- Root certificate: `certs/prod-ca-2021.crt`

The target connection verifies the server certificate using the configured CA certificate.

## 8. Connection Setup Instructions

1. Create a `.env` file in the project root.
2. Copy the configuration structure from `.env.example`.
3. Populate the source and target database credentials.
4. Ensure the target SSL certificate exists at the configured path.
5. Install the project dependencies from `requirements.txt`.
6. Run the connection validation script:

```bash
python test_connections.py
```

Successful connections should be reported for all three database environments.

## 9. Security Guidelines

- Never commit `.env` or actual database credentials.
- Use read-only credentials for source databases.
- Keep source and target database credentials separate.
- Use SSL for all database connections.
- Store database credentials in environment variables rather than hardcoding them in Python scripts.
- Keep the target warehouse CA certificate available for SSL verification.

---

**End of Warehouse Connection Documentation**