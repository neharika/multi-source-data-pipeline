
from src.extract.ecom_extract import extract_ecom_tables
from src.extract.saas_extract import extract_saas_tables
from src.load.loaders import load_chunks
from src.monitoring import validate_row_counts, write_manifest
from src.db import get_ecom_engine, get_saas_engine


def run_pipeline():
    """Extract, load, and validate both source databases."""

    print("\n========== E-COMMERCE DATA PIPELINE ==========\n")

    ecom_engine = get_ecom_engine()

    try:
        ecom_counts = load_chunks(
            extract_ecom_tables(),
            target_schema="raw_ecom",
            source_engine=ecom_engine,
            source_schema="ecom"
        )

        print("\n========== E-COMMERCE VALIDATION ==========\n")

        ecom_validation = validate_row_counts(
            source_engine=ecom_engine,
            source_schema="ecom",
            target_schema="raw_ecom"
        )

    finally:
        ecom_engine.dispose()

    print("\n========== SAAS DATA PIPELINE ==========\n")

    saas_engine = get_saas_engine()

    try:
        saas_counts = load_chunks(
            extract_saas_tables(),
            target_schema="raw_saas",
            source_engine=saas_engine,
            source_schema="saas"
        )

        print("\n========== SAAS VALIDATION ==========\n")

        saas_validation = validate_row_counts(
            source_engine=saas_engine,
            source_schema="saas",
            target_schema="raw_saas"
        )

    finally:
        saas_engine.dispose()

    all_validation = ecom_validation + saas_validation

    write_manifest(
        ecom_validation=ecom_validation,
        saas_validation=saas_validation
    )

    passed = sum(
        result["status"] == "PASS"
        for result in all_validation
    )

    failed = len(all_validation) - passed

    print("\n========== FINAL PIPELINE SUMMARY ==========")
    print(f"E-commerce tables loaded: {len(ecom_counts)}")
    print(f"SaaS tables loaded: {len(saas_counts)}")
    print(f"Total tables validated: {len(all_validation)}")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")

    if failed:
        print("\nWARNING: Some row counts do not match.")
        raise RuntimeError(
            f"Pipeline validation failed for {failed} tables."
        )

    print("\nAll source and target row counts match.")

    return {
        "ecom_counts": ecom_counts,
        "saas_counts": saas_counts,
        "validation": all_validation
    }


if __name__ == "__main__":
    run_pipeline()
