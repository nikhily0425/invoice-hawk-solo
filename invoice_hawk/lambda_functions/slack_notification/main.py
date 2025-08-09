"""
Lambda handler to post an invoice approval request to Slack.

Given an invoice ID, this function constructs a Slack message summarising
the invoice details and includes interactive buttons for “Approve” and
“Reject”.  Clicking a button triggers an API Gateway endpoint (not
implemented here) that will update the invoice status and continue the
workflow.
"""

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from invoice_hawk.models import Base, Invoice, LineItem, AuditLog
from invoice_hawk.utils import send_slack_message


def _get_db_session() -> Session:
    db_url = os.environ.get("DATABASE_URL")
    engine = create_engine(db_url)
    Base.metadata.create_all(engine)
    return Session(engine)


def _build_slack_message(invoice: Invoice) -> dict:
    total = float(invoice.total)
    lines_str = "\n".join(
        [f"• {li.quantity} × {li.description} @ ${float(li.price):.2f}" for li in invoice.line_items]
    )
    text = (
        f"*Invoice {invoice.invoice_number} from {invoice.vendor}*\n"
        f"Total: ${total:.2f}\n"
        f"PO: {invoice.purchase_order_number}\n\n"
        f"Line Items:\n{lines_str}"
    )
    attachments = [
        {
            "text": "Please review this invoice.",
            "fallback": "You are unable to approve this invoice",
            "callback_id": f"invoice_{invoice.id}",
            "color": "#3AA3E3",
            "attachment_type": "default",
            "actions": [
                {
                    "name": "approve",
                    "text": "Approve ✅",
                    "type": "button",
                    "style": "primary",
                    "value": str(invoice.id),
                    "action_id": "approve_invoice",
                },
                {
                    "name": "reject",
                    "text": "Reject ❌",
                    "type": "button",
                    "style": "danger",
                    "value": str(invoice.id),
                    "action_id": "reject_invoice",
                },
            ],
        }
    ]
    return {"text": text, "attachments": attachments}


def handler(event, context):  # pragma: no cover - entry point called by AWS
    invoice_id = event.get("invoice_id")
    if not invoice_id:
        raise ValueError("invoice_id is required")
    session = _get_db_session()
    invoice = session.get(Invoice, invoice_id)
    if not invoice:
        session.close()
        raise ValueError(f"Invoice {invoice_id} not found")
    payload = _build_slack_message(invoice)
    webhook_url = os.environ.get("SLACK_WEBHOOK_URL")
    if not webhook_url:
        session.close()
        raise RuntimeError("SLACK_WEBHOOK_URL environment variable is not set")
    send_slack_message(webhook_url, payload["text"], attachments=payload["attachments"])
    invoice.status = "awaiting_approval"
    session.add(
        AuditLog(
            invoice=invoice,
            event_type="slack_notification",
            details={"sent": True},
        )
    )
    session.commit()
    session.close()
    return {"sent": True, "invoice_id": invoice_id}