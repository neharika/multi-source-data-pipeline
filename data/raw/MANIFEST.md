# Raw Data Landing Manifest

**Extraction and validation timestamp:** 2026-11-24T22:44:09+05:30

## Landing Summary

| Source | Target schema | Tables | Source rows | Target rows |
|---|---|---:|---:|---:|
| E-commerce | `raw_ecom` | 11 | 944,414 | 944,414 |
| SaaS | `raw_saas` | 6 | 67,395 | 67,395 |

**Total source rows:** 1,011,809

**Total target rows:** 1,011,809

**Validation:** 17 passed, 0 failed

## Table-Level Validation

| Source | Target table | Source rows | Target rows | Status |
|---|---|---:|---:|---|
| E-commerce | `raw_ecom.orders` | 40,000 | 40,000 | PASS |
| E-commerce | `raw_ecom.order_items` | 81,806 | 81,806 | PASS |
| E-commerce | `raw_ecom.order_status_history` | 158,414 | 158,414 | PASS |
| E-commerce | `raw_ecom.customers` | 10,000 | 10,000 | PASS |
| E-commerce | `raw_ecom.products` | 4,000 | 4,000 | PASS |
| E-commerce | `raw_ecom.payment_transactions` | 40,034 | 40,034 | PASS |
| E-commerce | `raw_ecom.shipments` | 32,089 | 32,089 | PASS |
| E-commerce | `raw_ecom.sessions` | 100,000 | 100,000 | PASS |
| E-commerce | `raw_ecom.session_events` | 292,903 | 292,903 | PASS |
| E-commerce | `raw_ecom.attribution_touches` | 100,000 | 100,000 | PASS |
| E-commerce | `raw_ecom.devices` | 85,168 | 85,168 | PASS |
| SaaS | `raw_saas.events` | 53,534 | 53,534 | PASS |
| SaaS | `raw_saas.subscriptions` | 2,113 | 2,113 | PASS |
| SaaS | `raw_saas.subscription_events` | 3,741 | 3,741 | PASS |
| SaaS | `raw_saas.invoices` | 4,201 | 4,201 | PASS |
| SaaS | `raw_saas.users` | 2,556 | 2,556 | PASS |
| SaaS | `raw_saas.accounts` | 1,250 | 1,250 | PASS |

## Validation Notes

- Only the 17 configured source tables are included.
- Source counts are obtained using exact SQL `COUNT(*)` queries.
- Target counts are obtained after the raw data load.
- PASS indicates matching source and target row counts.
