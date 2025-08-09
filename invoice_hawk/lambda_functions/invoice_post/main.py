"""
Lambda handler to finalise invoice processing after approval.

Triggered by a Slack interactive callback (e.g. via API Gateway).  The event
payload includes the invoice ID and the user’s decision (approve or
reject).  If approved, the invoice is posted to NetSuite (test mode) via
the sandbox API.  The invoice status and audit log are updated
accordingly.
"""

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from invoice_hawk.models import Base, Invoice, AuditLog
from invoice_hawk.netsuite_client import NetSuiteClient


def _get_db_session() -> Session:
    db_url = os.environ.get("DATABASE_URL")
    engine = create_engine(db_url)
    Base.metadata.create_all(engine)
    return Session(engine)


def handler(event, context):  # pragma: no cover - entry point called by AWS
    invoice_id = event.get("invoice_id")
    decision = event.get("decision")  # "approve" or "reject"
    if not invoice_id or decision not in {"approve", "reject"}:
        raise ValueError("Both invoice_id and a valid decision are required")
    session = _get_db_session()
    invoice = session.get(Invoice, invoice_id)
    if not invoice:
        session.close()
        raise ValueError(f"Invoice {invoice_id} not found")
    netsuite = NetSuiteClient()
    if decision == "approve":
        ns_response = netsuite.post_invoice(
            {
                "invoice_number": invoice.invoice_number,
                "vendor": invoice.vendor,
                "invoice_date": invoice.invoice_date,
                "total": float(invoice.total),
                "purchase_order_number": invoice.purchase_order_number,
                "line_items": [
                    {
                        "description": li.description,
                        "quantity": li.quantity,
                        "price": float(li.price),
                    }
                    for li in invoice.line_items
                ],
            }
        )
        invoice.status = "approved"
        audit_details = {"decision": decision, "netsuite_response": ns_response}
    else:
        invoice.status = "rejected"
        audit_details = {"decision": decision}
    session.add(
        AuditLog(
            invoice=invoice,
            event_type="invoice_post",
            details=audit_details,
        )
    )
    session.commit()
    session.close()
    return {"invoice_id": invoice_id, "decision": decision}