"""
Tests for S3 key naming in the CLI archiving logic.

The ``process_file`` function uploads raw PDFs and the extracted JSON
representation to S3 when an archive bucket is configured.  We
monkeypatch the ``upload_file_to_s3`` function to capture the keys used
for storing the JSON and assert that they follow the expected pattern:

``json/{year}/{month}/{day}/{vendor}/{invoice_number}.json``

Vendor names and invoice numbers may include spaces or slashes; these
characters should be normalised to underscores to form valid S3 keys.
"""

import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from invoice_hawk.models import Base
from invoice_hawk.cli import process_file


def test_json_key_naming(tmp_path, monkeypatch):
    # Create a temporary PDF file
    pdf_path = tmp_path / "inv 001.pdf"
    pdf_path.write_bytes(b"dummy")

    # Define extracted invoice data
    extracted = {
        "vendor": "Test Vendor/Inc",
        "invoice_number": "INV/001",
        "invoice_date": "2025-07-30",
        "total": 10.0,
        "purchase_order_number": "PO-123",
        "line_items": [
            {"description": "Item", "quantity": 1, "price": 10.0},
        ],
    }

    # Monkeypatch get_provider().extract_fields to return our extracted dict
    class DummyProvider:
        def extract_fields(self, content):  # type: ignore[override]
            return extracted

    # Monkeypatch NetSuiteClient.get_purchase_order to avoid network
    class DummyNS:
        def get_purchase_order(self, po):  # type: ignore[override]
            return {"lines": [{"quantity": 1, "price": 10.0}]}

    # Capture the uploaded keys
    uploaded = {"json_key": None, "raw_key": None}

    def fake_upload_file_to_s3(content, bucket, key, content_type):  # type: ignore[override]
        if content_type == "application/pdf":
            uploaded["raw_key"] = key
        else:
            uploaded["json_key"] = key

    # Set environment variables
    monkeypatch.setenv("ARCHIVE_BUCKET", "test-bucket")
    # Replace the upload function
    monkeypatch.setattr("invoice_hawk.cli.upload_file_to_s3", fake_upload_file_to_s3)
    # Prepare a SQLite database
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = Session(engine)

    # Run the process_file function
    process_file(pdf_path, session, DummyProvider(), DummyNS(), slack_webhook=None)
    session.close()

    # Check that both raw and JSON keys were set
    assert uploaded["raw_key"] is not None
    assert uploaded["json_key"] is not None
    # The JSON key should normalise spaces and slashes and match the date
    assert uploaded["json_key"].startswith("json/2025/07/30/")
    assert "Test_Vendor_Inc" in uploaded["json_key"]
    assert uploaded["json_key"].endswith("INV_001.json")