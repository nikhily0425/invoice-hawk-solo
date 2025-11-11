# Invoice Hawk – Solo MVP

This repository contains a prototype implementation of **Invoice Hawk**, an automated accounts payable (AP) pipeline.  The MVP ingests PDF invoices, extracts key fields via GPT‑powered OCR, performs a two‑way match against NetSuite purchase orders, sends Slack notifications for approval, and posts approved invoices back to NetSuite.  A CLI runner ties the components together for local testing.

## Features

* **Email ingestion** – A scheduled process connects to IMAP, downloads invoice attachments, and uploads them to S3.  For local development the CLI can read PDFs from a folder.
* **OCR extraction** – Uses a pluggable provider pattern (`invoice_hawk/ocr_provider.py`) with a GPT Vision provider and a fallback parser for tests.  Extracted fields include vendor, invoice number, date, total, purchase order number, quantities, and prices.
* **Two‑way match** – Retrieves purchase order data from NetSuite (stubbed client in `invoice_hawk/netsuite_client.py`) and checks that quantities and prices are within ±1 % and ±2 % tolerances, respectively.
* **Slack notifications** – Sends interactive messages with Approve/Reject links via incoming webhook.  Actions trigger further processing to post to NetSuite or mark the invoice as rejected.
* **CLI runner** – The `invoice_hawk/cli.py` module orchestrates ingestion, OCR, matching, and Slack notification for one or more PDFs.  This is useful for local development and unit tests.
* **Database models** – SQLAlchemy models for `invoices`, `line_items`, and `audit_log` tables are defined in `invoice_hawk/models.py`.

## Repository structure

```
invoice-hawk-solo/
├── README.md             # this file
├── invoice_hawk/         # core application code
│   ├── __init__.py
│   ├── models.py         # SQLAlchemy models
│   ├── utils.py          # shared helpers (S3 upload, Slack, etc.)
│   ├── ocr_provider.py   # OCR provider pattern with GPT Vision & fallback
│   ├── netsuite_client.py# NetSuite client stubs (PO lookup & invoice post)
│   ├── cli.py            # CLI runner for local testing
│   └── lambda_functions/ # AWS Lambda handlers (ingest, extract, match, slack, post)
│       ├── ingest_email_to_s3/main.py
│       ├── ocr_extract/main.py
│       ├── po_lookup/main.py
│       ├── slack_notification/main.py
│       └── invoice_post/main.py
├── tests/                # unit tests (pytest)
│   ├── test_models.py
│   ├── test_po_lookup.py
│   └── test_ocr_provider.py
├── docker-compose.yml    # local Postgres instance
├── requirements.txt      # Python dependencies
└── week2_status.json     # weekly status report
```

## Development

The project uses Python 3.11, SQLAlchemy for database interactions, and the `slack_sdk` for sending messages.  To develop locally:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
docker-compose up -d  # start Postgres

# run unit tests
pytest --cov=invoice_hawk

# run the CLI on sample PDFs
python -m invoice_hawk.cli --input /path/to/invoices/*.pdf
```

The OCR provider defaults to the fallback parser in test mode.  To enable GPT Vision extraction, set `OCR_PROVIDER=gpt` and provide the necessary OpenAI API key via `OPENAI_API_KEY` environment variable.

## Deployment

The `serverless deploy` command will output the URL of the OCR and Slack API endpoints. These endpoints are used by the smoke test script.

### Staging deployment

To deploy a staging environment in AWS, ensure the required environment variables (`DATABASE_URL`, `SLACK_SIGNING_SECRET`, etc.) are configured in your deployment environment (for example via AWS Systems Manager Parameter Store or Secrets Manager). Then run:

```bash
serverless deploy --stage staging
```

This command will create or update the Lambda functions (`ocrWorker`, `slackActions`, and `invoicePost`), the HTTP API Gateway, and the S3 archive bucket (if not provided). All resources are tagged with `project=invoice-hawk` and `env=staging` for cost tracking.

### Dry-run deployment from CI

The CI pipeline includes a `deploy-dryrun` job that runs `serverless package --stage dev` to validate that the Serverless stack can be synthesized without deploying. You can manually trigger this job via the GitHub Actions “Run workflow” button or by pushing a git tag matching `v*`. The dry-run uses AWS OpenID Connect (OIDC) to assume a role specified in the `AWS_ROLE_TO_ASSUME` secret.

### Smoke test verification checklist

After deploying to a staging environment, verify the following endpoints respond as expected:

1. **OCR endpoint** (`/ocr`) – Send a small base64‑encoded PDF and ensure the JSON response contains `vendor`, `invoice_number`, and `total` fields.
2. **Slack actions endpoint** (`/slack/actions`) – Craft a signed payload with a known invoice ID and verify the response contains `{ "ok": true }`. Confirm that the invoice status and audit log update in the database.
3. **Invoice post endpoint** (`/invoice/post`) – POST a JSON body with `{ "invoice_id": <id> }` and verify the JSON response includes a `posted` flag and an `external_id`.

You can use the updated `scripts/smoke.sh` script to automate these checks.
