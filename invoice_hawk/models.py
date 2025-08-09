"""
Database models for Invoice Hawk.

These SQLAlchemy models define the schema used for persisting invoice metadata, line
items, and audit events.  Migrations are intentionally omitted in this MVP; the
schema can be initialised via SQLAlchemy’s metadata create functions.
"""

import datetime as _dt
from sqlalchemy import (
    Column,
    Integer,
    String,
    Date,
    DateTime,
    Numeric,
    ForeignKey,
    JSON,
    Float,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class Invoice(Base):
    """Represents a vendor invoice extracted from a PDF."""

    __tablename__ = "invoices"

    id = Column(Integer, primary_key=True)
    vendor = Column(String, nullable=False)
    invoice_number = Column(String, nullable=False, unique=True)
    invoice_date = Column(Date, nullable=False)
    total = Column(Numeric(10, 2), nullable=False)
    purchase_order_number = Column(String, nullable=False)
    status = Column(
        String,
        nullable=False,
        default="pending",  # possible values: pending, matched, flagged, awaiting_approval, approved, rejected, error
    )
    created_at = Column(DateTime, default=_dt.datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=_dt.datetime.utcnow, onupdate=_dt.datetime.utcnow)

    # relationships
    line_items = relationship("LineItem", back_populates="invoice", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="invoice", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Invoice id={self.id} number={self.invoice_number} vendor={self.vendor}>"


class LineItem(Base):
    """Represents a single line item extracted from an invoice."""

    __tablename__ = "line_items"

    id = Column(Integer, primary_key=True)
    invoice_id = Column(Integer, ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False)
    description = Column(String, nullable=True)
    quantity = Column(Float, nullable=False)
    price = Column(Numeric(10, 2), nullable=False)
    created_at = Column(DateTime, default=_dt.datetime.utcnow, nullable=False)

    invoice = relationship("Invoice", back_populates="line_items")

    def __repr__(self) -> str:
        return (
            f"<LineItem id={self.id} invoice_id={self.invoice_id} qty={self.quantity} price={self.price}>"
        )


class AuditLog(Base):
    """Audit log capturing events across the invoice lifecycle."""

    __tablename__ = "audit_log"

    id = Column(Integer, primary_key=True)
    invoice_id = Column(Integer, ForeignKey("invoices.id", ondelete="CASCADE"), nullable=True)
    event_type = Column(String, nullable=False)
    details = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=_dt.datetime.utcnow, nullable=False)

    invoice = relationship("Invoice", back_populates="audit_logs")

    def __repr__(self) -> str:
        return f"<AuditLog id={self.id} invoice_id={self.invoice_id} event={self.event_type}>"