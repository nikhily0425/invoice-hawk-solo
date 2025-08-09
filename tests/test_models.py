import datetime as dt

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from invoice_hawk.models import Base, Invoice, LineItem, AuditLog


def test_invoice_lineitem_relationship(tmp_path):
    # Use a temporary SQLite database for testing
    db_path = tmp_path / "test.db"
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    session = Session(engine)
    # create invoice
    invoice = Invoice(
        vendor="Test Vendor",
        invoice_number="TEST-001",
        invoice_date=dt.date(2025, 7, 24),
        total=200.00,
        purchase_order_number="PO-TEST",
    )
    invoice.line_items.append(LineItem(description="Item", quantity=2, price=100.0))
    session.add(invoice)
    session.commit()
    # fetch and verify
    fetched = session.query(Invoice).filter_by(invoice_number="TEST-001").first()
    assert fetched is not None
    assert len(fetched.line_items) == 1
    assert fetched.line_items[0].quantity == 2
    # audit log not automatically created
    assert fetched.audit_logs == []
    session.close()