"""
Lambda handler to extract invoice fields from a PDF using a pluggable OCR
provider.

Triggered by an S3 object creation event.  Downloads the PDF from S3,
submits it to the selected OCR provider, parses the returned JSON for key
fields (vendor, invoice number, date, total, PO number, line quantities and
prices), and stores the structured data in the Postgres database.
"""

import os
from typing import Any, Dict

import boto3
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from invoice_hawk.models import Base, Invoice, LineItem, AuditLog
from invoice_hawk.ocr_provider import get_provider


def _download_pdf(bucket: str, key: str) -> bytes:
    s3 = boto3.client("s3")
    obj = s3.get_object(Bucket=bucket, Key=key)
    return obj["Body"].read()


def _get_db_session() -> Session:
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        raise RuntimeError("DATABASE_URL environment variable is not set")
    engine = create_engine(db_url)
    Base.metadata.create_all(engine)
    return Session(engine)


def _persist_invoice(session: Session, data: Dict[str, Any]) -> int:
    invoice = Invoice(
        vendor=data["vendor"],
        invoice_number=data["invoice_number"],
        invoice_date=data["invoice_date"],
        total=data["total"],
        purchase_order_number=data["purchase_order_number"],
    )
    for li in data.get("line_items", []):
        invoice.line_items.append(
            LineItem(
                description=li.get("description"),
                quantity=li.get("quantity", 0),
                price=li.get("price", 0),
            )
        )
    session.add(invoice)
    session.add(
        AuditLog(
            invoice=invoice,
            event_type="extracted",
            details=data,
        )
    )
    session.commit()
    invoice_id = invoice.id
    return invoice_id


def handler(event, context):  # pragma: no cover - entry point called by AWS
    record = event.get("Records", [])[0]
    bucket = record["s3"]["bucket"]["name"]
    key = record["s3"]["object"]["key"]
    content = _download_pdf(bucket, key)
    provider = get_provider()
    extracted = provider.extract_fields(content)
    session = _get_db_session()
    invoice_id = _persist_invoice(session, extracted)
    session.close()
    return {"invoice_id": invoice_id, "status": "extracted"}