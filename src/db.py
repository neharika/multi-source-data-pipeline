
import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import URL


# Load environment variables from the project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")


def create_db_engine(prefix, ssl_args=None):
    """
    Create a SQLAlchemy engine using environment variables.

    prefix: ECOM, SAAS, or TARGET
    ssl_args: PostgreSQL SSL connection settings
    """

    required_vars = [
        f"{prefix}_DB_USER",
        f"{prefix}_DB_PASS",
        f"{prefix}_DB_HOST",
        f"{prefix}_DB_PORT",
        f"{prefix}_DB_NAME",
    ]

    missing = [var for var in required_vars if not os.getenv(var)]

    if missing:
        raise ValueError(
            f"Missing environment variables: {', '.join(missing)}"
        )

    connection_url = URL.create(
        drivername="postgresql+psycopg2",
        username=os.getenv(f"{prefix}_DB_USER"),
        password=os.getenv(f"{prefix}_DB_PASS"),
        host=os.getenv(f"{prefix}_DB_HOST"),
        port=int(os.getenv(f"{prefix}_DB_PORT")),
        database=os.getenv(f"{prefix}_DB_NAME"),
    )

    return create_engine(
        connection_url,
        connect_args=ssl_args or {},
        pool_pre_ping=True,
    )


# Source database engines (read-only credentials)
def get_ecom_engine():
    return create_db_engine(
        "ECOM",
        ssl_args={"sslmode": "require"},
    )


def get_saas_engine():
    return create_db_engine(
        "SAAS",
        ssl_args={"sslmode": "require"},
    )


# Target warehouse engine (Neon)
def get_target_engine():
    return create_db_engine(
        "TARGET",
        ssl_args={
            "sslmode": os.getenv("TARGET_DB_SSLMODE", "require"),
        },
    )
