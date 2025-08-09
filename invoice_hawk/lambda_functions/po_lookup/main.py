"""
Lambda handler to perform NetSuite PO lookup and two‑way matching.

Given an invoice ID (triggered after extraction), this function retrieves
corresponding purchase order data from NetSuite via the client stub, compares
line quantities and prices within tolerances (±2 % for price, ±1 % for
quantity), and updates the invoice status accordingly.  Results are written
to the audit log.
"""

import os
from typing import Dict, List

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from invoice_hawk.models import Base, Invoice, LineItem, AuditLog
from invoice_hawk.netsuite_client import NetSuiteClient


PRICE_TOLERANCE = 0.02  # ±2 %
QTY_TOLERANCE = 0.01    # ±1 %


def _get_db_session() -> Session:
    db_url = os.environ.get("DATABASE_URL")
    engine = create_engine(db_url)
    Base.metadata.create_all(engine)
    return Session(engine)


def _compare_lines(
    invoice_lines: List[LineItem], po_lines: List[Dict[str, float]]
) -> bool:
    """Return True if all invoice lines are within tolerance of PO lines."""
    for i, invoice_li in enumerate(invoice_lines):
        # If the purchase order has fewer lines than the invoice, fail immediately
        if i >= len(po_lines):
            return False
        po_li = po_lines[i]
        po_qty = po_li.get("quantity", 0)
        po_price = po_li.get("price", 0)
        # Compute tolerance thresholds relative to the invoice values rather than the PO.
        # Using the invoice as the basis aligns with test expectations: a 1 % quantity
        # tolerance on an invoice quantity of 5 allows a difference of 0.05, so a PO
        # quantity of 4.95 is considered within tolerance. Similarly, a ±2 % price
        # tolerance on an invoice price of 100 allows a ±2.0 difference.
        qty_tol = QTY_TOLERANCE * invoice_li.quantity if invoice_li.quantity else 0
        price_tol = PRICE_TOLERANCE * float(invoice_li.price) if invoice_li.price else 0
        qty_ok = abs(invoice_li.quantity - po_qty) <= qty_tol
        price_ok = abs(float(invoice_li.price) - po_price) <= price_tol
        if not (qty_ok and price_ok):
            return False
    return True


def handler(event, context):  # pragma: no cover - entry point called by AWS
    invoice_id = event.get("invoice_id")
    if not invoice_id:
        raise ValueError("invoice_id is required")
    session = _get_db_session()
    invoice = session.get(Invoice, invoice_id)
    if not invoice:
        session.close()
        raise ValueError(f"Invoice {invoice_id} not found")
    netsuite = NetSuiteClient()
    po_data = netsuite.get_purchase_order(invoice.purchase_order_number)
    within_tolerance = _compare_lines(invoice.line_items, po_data.get("lines", []))
    invoice.status = "matched" if within_tolerance else "flagged"
    # audit log
    session.add(
        AuditLog(
            invoice=invoice,
            event_type="po_check",
            details={
                "po_data": po_data,
                "within_tolerance": within_tolerance,
            },
        )
    )
    session.commit()
    response = {
        "invoice_id": invoice_id,
        "within_tolerance": within_tolerance,
    }
    session.close()
    return response