# Invoice Hawk – Solo MVP

Invoice Hawk is a **prototype automated Accounts Payable (AP) pipeline**:

- Ingests PDF invoices (email → S3 or local folder)
- Runs OCR (GPT Vision or fallback) to extract key invoice fields
- Performs a **two-way match** against NetSuite purchase orders
- Sends interactive **Slack approval** messages (Approve / Reject)
- On approval, can **post invoices to NetSuite** and store the external ID
- Includes a **CLI runner**, **AWS Lambda deployment** via Serverless, and **smoke tests**

This repo is built as a solo MVP, but structured as if it will grow into a production system.

---

## High-level architecture

At a high level, the system has these moving parts:

1. **Ingestion**
   - (Lambda) `ingest_email_to_s3`: pulls invoices from email and stores PDFs in S3.
   - (Local) `app/ingest_imap.py`: a dev helper to simulate email ingestion locally.

2. **OCR & Matching**
   - `invoice_hawk/ocr_provider.py` – pluggable OCR providers (GPT Vision + fallback).
   - `invoice_hawk/netsuite_client.py` – NetSuite stub client:
     - Purchase order lookup for two-way match.
     - Posting approved invoices (in test mode, returns deterministic `external_id`).
   - `invoice_hawk/models.py` – SQLAlchemy models for:
     - `Invoice`, `LineItem`, `AuditLog` (+ `external_id` on invoices).
   - `invoice_hawk/cli.py` – local runner:
     - Reads PDFs, extracts fields, persists invoice + line items,
     - Runs two-way match, updates status, sends Slack notifications.

3. **Approvals & Posting**
   - `invoice_hawk/slack_app.py` – Slack interactive actions:
     - Approve / Reject buttons.
     - Updates invoice status and writes `AuditLog`.
     - On approval, calls NetSuite client to “post” and sets `external_id` in test mode.
   - `invoice_hawk/lambda_functions/invoice_post/main.py` – HTTP API Lambda to post an invoice by `invoice_id`.

4. **AWS Deployment**
   - `serverless.yml` – defines:
     - `ocrWorker` (OCR Lambda, S3 + HTTP event),
     - `slackActions` (Slack interactive HTTP endpoint),
     - `invoicePost` (HTTP endpoint to post invoices),
     - S3 archive bucket and tagging (`project=invoice-hawk`, `env=<stage>`).
   - `scripts/smoke.sh` – smoke tests for:
     - `/ocr`
     - `/slack/actions`
     - `/invoice/post` (if `INVOICE_POST_URL` is set)

5. **Tooling & CI/CD**
   - `docker-compose.yaml` – local Postgres.
   - `.github/workflows/ci.yml` – CI including:
     - Tests on each push/PR,
     - `deploy-dryrun` job running `serverless package --stage dev` with AWS OIDC.

For a deeper architectural breakdown, see [`docs/architecture.md`](docs/architecture.md).

---

## Repository layout

```text
invoice-hawk-solo/
├── app/                         # Early / local app scripts (IMAP, OCR, matching, Slack)
│   ├── ingest_imap.py
│   ├── ocr_extract.py
│   ├── match_po.py
│   ├── slack_notify.py
│   └── post_netsuite.py
├── invoice_hawk/                # Core package (used by Lambdas & CLI)
│   ├── __init__.py
│   ├── cli.py                   # Local CLI orchestrator
│   ├── models.py                # SQLAlchemy models: Invoice, LineItem, AuditLog
│   ├── netsuite_client.py       # NetSuite test client (PO + invoice post, with retry)
│   ├── ocr_provider.py          # GPT Vision + fallback OCR providers
│   ├── slack_app.py             # FastAPI app for Slack interactive actions
│   └── lambda_functions/
│       ├── ingest_email_to_s3/main.py
│       ├── ocr_extract/main.py
│       ├── po_lookup/main.py
│       ├── slack_notification/main.py
│       └── invoice_post/main.py
├── scripts/
│   └── smoke.sh                 # Curl-based smoke tests for deployed endpoints
├── tests/                       # Pytest unit tests (16 total)
│   ├── conftest.py
│   ├── test_ocr_provider.py
│   ├── test_ocr_provider_impl.py
│   ├── test_po_lookup.py
│   ├── test_models.py
│   ├── test_match.py
│   ├── test_s3_key_naming.py
│   ├── test_slack_signature.py
│   └── test_netsuite_retry.py
├── docker-compose.yaml          # Local Postgres
├── serverless.yml               # Serverless Framework configuration
├── README.md                    # (You are here)
├── SECURITY.md                  # Security & secrets notes
├── deploy_checklist.md          # Manual deployment/runbook checklist
├── requirements.txt             # Python dependencies
├── week2_patch.diff / week2_status.json
├── week3_patch.diff / week3_status.json
├── week4_patch.diff / week4_status.json
├── week5_patch.diff / week5_status.json
├── week6_patch.diff / week6_status.json
├── week7_patch.diff / week7_status.json
└── docs/                        # (You will add this) Full project documentation