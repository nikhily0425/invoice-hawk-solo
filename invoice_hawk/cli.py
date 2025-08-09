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

# Tolerance constants (matching those in po_lookup/main.py)
PRICE_TOLERANCE = 0.02
QTY_TOLERANCE = 0.01


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


def persist_invoice(session: Session, data: dict) -> Invoice:
    invoice = Invoice(
        vendor=data["vendor"],
        invoice_number=data["invoice_number"],
        invoice_date=data["invoice_date"],
        total=data["total"],
        purchase_order_number=data["purchase_order_number"],
    )
    for li in data.get("line_items", []):
        invoice.line_items.append(LineItem(description=li.get("description"), quantity=li.get("quantity", 0), price=li.get("price", 0)))
    session.add(invoice)
    session.add(AuditLog(invoice=invoice, event_type="extracted", details=data))
    session.commit()
    return invoice


def process_file(path: Path, session: Session, provider, netsuite: NetSuiteClient, slack_webhook: str | None) -> None:
    content = path.read_bytes()
    extracted = provider.extract_fields(content)
    invoice = persist_invoice(session, extracted)
    # two‑way match
    po = netsuite.get_purchase_order(invoice.purchase_order_number)
    within = compare_lines(invoice.line_items, po.get("lines", []))
    invoice.status = "matched" if within else "flagged"
    session.add(AuditLog(invoice=invoice, event_type="po_check", details={"within_tolerance": within, "po_data": po}))
    session.commit()
    print(f"Processed {path.name}: matched={within}")
    # Slack notification
    if slack_webhook:
        # build simple Slack message
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