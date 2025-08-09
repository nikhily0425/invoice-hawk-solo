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
