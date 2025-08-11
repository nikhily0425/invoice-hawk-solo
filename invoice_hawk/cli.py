"""
Command‑line interface for Invoice Hawk.

This script orchestrates the end‑to‑end invoice processing pipeline for
development and testing.  It reads one or more PDF files, performs OCR
extraction, matches against purchase orders, sends Slack notifications,
and optionally posts approved invoices.  In production these steps run in
AWS Lambda; here they are combined for convenience.
"""

from __future__ import annotations

import argparse
import glob
import json
import os
from pathlib import Path
from typing import Iterable

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from .models import Base, Invoice, LineItem, AuditLog
from .ocr_provider import get_provider
from .netsuite_client import NetSuiteClient
from .utils import send_slack_message

from datetime import date, datetime
import json, os, re

# Tolerance constants (matching those in po_lookup/main.py)
PRICE_TOLERANCE = 0.02
QTY_TOLERANCE = 0.01


# --- test hook: monkeypatched by tests ---
def upload_file_to_s3(content: bytes, bucket: str, key: str, content_type: str) -> None:
    """
    Minimal stub so tests can monkeypatch this function.
    Real impl can call boto3.client('s3').put_object(...).
    """
    return

def _inv_key(s: str | None) -> str:
    # Preserve letters but force UPPERCASE; replace separators with underscores
    import re
    return re.sub(r"[^A-Za-z0-9]+", "_", (s or "unknown")).strip("_").upper()

def _vendor_key(s: str | None) -> str:
    # Preserve case; replace spaces, slashes, hyphens, etc. with underscores
    import re
    return re.sub(r"[^A-Za-z0-9]+", "_", (s or "unknown")).strip("_")

def _as_date(value) -> date | None:
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value).date()
        except ValueError:
            return None
    return None

def _slug(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]+", "-", (s or "unknown")).strip("-").lower()

def compare_lines(invoice_lines: Iterable[LineItem], po_lines: Iterable[dict]) -> bool:
    for i, inv_li in enumerate(invoice_lines):
        try:
            po_li = list(po_lines)[i]
        except IndexError:
            return False
        # Compute tolerance thresholds relative to the invoice values rather than the PO.
        qty_tol = QTY_TOLERANCE * inv_li.quantity if inv_li.quantity else 0
        price_tol = PRICE_TOLERANCE * float(inv_li.price) if inv_li.price else 0
        qty_ok = abs(inv_li.quantity - po_li.get("quantity", 0)) <= qty_tol
        price_ok = abs(float(inv_li.price) - po_li.get("price", 0)) <= price_tol
        if not (qty_ok and price_ok):
            return False
    return True


def persist_invoice(session, extracted: dict):
    from .models import Invoice, LineItem

    inv_date = _as_date(extracted.get("invoice_date"))

    invoice = Invoice(
        vendor=extracted.get("vendor"),
        invoice_number=extracted.get("invoice_number"),
        invoice_date=inv_date,               # <- must be a date object
        total=extracted.get("total", 0.0),
        purchase_order_number=extracted.get("purchase_order_number"),
        status="NEW",
    )
    session.add(invoice)
    session.flush()
    session.commit()
    return invoice


def process_file(path: Path, session: Session, provider, netsuite: NetSuiteClient, slack_webhook: str | None) -> None:
    content = path.read_bytes()
    extracted = provider.extract_fields(content)

    # persist
    invoice = persist_invoice(session, extracted)

    # two-way match
    po = netsuite.get_purchase_order(invoice.purchase_order_number)
    within = compare_lines(invoice.line_items, po.get("lines", []))
    invoice.status = "matched" if within else "flagged"
    session.add(AuditLog(invoice=invoice, event_type="po_check",
                         details={"within_tolerance": within, "po_data": po}))
    session.commit()
    print(f"Processed {path.name}: matched={within}")

    # Slack notification (optional)
    if slack_webhook:
        text = f"Invoice {invoice.invoice_number} from {invoice.vendor}: {'matched' if within else 'flagged'}"
        actions = [
            {
                "text": "Approve ✅",
                "type": "button",
                "style": "primary",
                "value": str(invoice.id),
                "action_id": "approve_invoice",
            },
            {
                "text": "Reject ❌",
                "type": "button",
                "style": "danger",
                "value": str(invoice.id),
                "action_id": "reject_invoice",
            },
        ]
        attachments = [
            {
                "text": "Please review this invoice.",
                "fallback": "You are unable to approve this invoice",
                "callback_id": f"invoice_{invoice.id}",
                "color": "#3AA3E3",
                "attachment_type": "default",
                "actions": actions,
            }
        ]
        send_slack_message(slack_webhook, text, attachments=attachments)
        invoice.status = "awaiting_approval"
        session.add(AuditLog(invoice=invoice, event_type="slack_notification", details={"sent": True}))
        session.commit()

    # --- archive to S3 (tests monkeypatch upload_file_to_s3) ---
    bucket = os.getenv("ARCHIVE_BUCKET")
    if bucket:
        # parse the invoice date -> date object (uses your helper)
        d = _as_date(extracted.get("invoice_date")) or date.today()
        yyyy = f"{d.year:04d}"
        mm   = f"{d.month:02d}"
        dd   = f"{d.day:02d}"

        vendor = _vendor_key(extracted.get("vendor"))   # -> "Test_Vendor_Inc"
        invno  = _inv_key(extracted.get("invoice_number"))  # was _slug(...)

        raw_key  = f"raw/{yyyy}/{mm}/{dd}/{vendor}/{invno}.pdf"
        json_key = f"json/{yyyy}/{mm}/{dd}/{vendor}/{invno}.json"

        # use the bytes we already read from `path`
        upload_file_to_s3(content, bucket, raw_key,  "application/pdf")
        upload_file_to_s3(json.dumps(extracted).encode("utf-8"), bucket, json_key, "application/json")



def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Invoice Hawk pipeline on local PDFs")
    parser.add_argument("--input", nargs="+", help="Glob pattern(s) for input PDF files", required=True)
    parser.add_argument("--database-url", default=os.environ.get("DATABASE_URL"), help="SQLAlchemy database URL")
    parser.add_argument("--slack-webhook", default=os.environ.get("SLACK_WEBHOOK_URL"), help="Slack webhook URL (optional)")
    args = parser.parse_args()
    if not args.database_url:
        raise SystemExit("DATABASE_URL must be provided via --database-url or environment variable")
    engine = create_engine(args.database_url)
    Base.metadata.create_all(engine)
    session = Session(engine)
    provider = get_provider()
    netsuite = NetSuiteClient()
    files = []
    for pattern in args.input:
        files.extend([Path(p) for p in glob.glob(pattern)])
    for path in files:
        process_file(path, session, provider, netsuite, args.slack_webhook)
    session.close()


if __name__ == "__main__":
    main()