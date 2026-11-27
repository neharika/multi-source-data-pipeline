
from datetime import datetime
from pathlib import Path

from sqlalchemy import text

from src.config import ECOM_TABLES, SAAS_TABLES
from src.db import get_target_engine


def validate_row_counts(source_engine, source_schema, target_schema):
    """
    Compare exact source and target row counts
    for the selected tables only.
    """

    table_mapping = {
        "ecom": ECOM_TABLES,
        "saas": SAAS_TABLES,
    }

    if source_schema not in table_mapping:
        raise ValueError(f"Invalid source schema: {source_schema}")

    allowed_target_schemas = {"raw_ecom", "raw_saas"}

    if target_schema not in allowed_target_schemas:
        raise ValueError(f"Invalid target schema: {target_schema}")

    target_engine = get_target_engine()
    validation_results = []

    try:
        tables = table_mapping[source_schema]

        for table in tables:

            source_query = text(
                f'SELECT COUNT(*) FROM "{source_schema}"."{table}"'
            )

            target_query = text(
                f'SELECT COUNT(*) FROM "{target_schema}"."{table}"'
            )

            with source_engine.connect() as conn:
                source_count = conn.execute(
                    source_query
                ).scalar_one()

            with target_engine.connect() as conn:
                target_count = conn.execute(
                    target_query
                ).scalar_one()

            passed = source_count == target_count

            result = {
                "table_name": table,
                "source_rows": source_count,
                "target_rows": target_count,
                "status": "PASS" if passed else "FAIL"
            }

            validation_results.append(result)

            print(
                f"{table}: source={source_count:,}, "
                f"target={target_count:,} — {result['status']}"
            )

        return validation_results

    finally:
        target_engine.dispose()


def write_manifest(ecom_validation, saas_validation):
    """Generate the raw landing manifest from validation results."""

    project_root = Path(__file__).resolve().parent.parent
    manifest_path = project_root / "data" / "raw" / "MANIFEST.md"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().astimezone().isoformat(
        timespec="seconds"
    )

    all_results = [
        ("E-commerce", "raw_ecom", ecom_validation),
        ("SaaS", "raw_saas", saas_validation),
    ]

    total_source = 0
    total_target = 0
    total_passed = 0
    total_failed = 0

    lines = [
        "# Raw Data Landing Manifest",
        "",
        f"**Extraction and validation timestamp:** {timestamp}",
        "",
        "## Landing Summary",
        "",
        "| Source | Target schema | Tables | Source rows | Target rows |",
        "|---|---|---:|---:|---:|",
    ]

    for source_name, target_schema, results in all_results:
        source_rows = sum(r["source_rows"] for r in results)
        target_rows = sum(r["target_rows"] for r in results)

        lines.append(
            f"| {source_name} | `{target_schema}` | "
            f"{len(results)} | {source_rows:,} | {target_rows:,} |"
        )

        total_source += source_rows
        total_target += target_rows
        total_passed += sum(r["status"] == "PASS" for r in results)
        total_failed += sum(r["status"] == "FAIL" for r in results)

    lines.extend([
        "",
        f"**Total source rows:** {total_source:,}",
        "",
        f"**Total target rows:** {total_target:,}",
        "",
        f"**Validation:** {total_passed} passed, {total_failed} failed",
        "",
        "## Table-Level Validation",
        "",
        "| Source | Target table | Source rows | Target rows | Status |",
        "|---|---|---:|---:|---|",
    ])

    for source_name, target_schema, results in all_results:
        for result in results:
            lines.append(
                f"| {source_name} | "
                f"`{target_schema}.{result['table_name']}` | "
                f"{result['source_rows']:,} | "
                f"{result['target_rows']:,} | "
                f"{result['status']} |"
            )

    lines.extend([
        "",
        "## Validation Notes",
        "",
        "- Only the 17 configured source tables are included.",
        "- Source counts are obtained using exact SQL `COUNT(*)` queries.",
        "- Target counts are obtained after the raw data load.",
        "- PASS indicates matching source and target row counts.",
        "",
    ])

    manifest_path.write_text("\n".join(lines), encoding="utf-8")

    print(f"\nManifest generated: {manifest_path}")
