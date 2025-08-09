"""
NetSuite client stubs for Invoice Hawk.

This module provides a simple class to interface with the NetSuite REST API.
Actual network requests are not implemented; instead, stub responses are
returned to allow downstream code and tests to proceed without external
dependencies.  Replace these stubs with real API calls once credentials
and endpoints are available.
"""

from __future__ import annotations

from typing import Any, Dict, List


class NetSuiteClient:
    def __init__(self, account: str | None = None, token: str | None = None) -> None:
        self.account = account
        self.token = token

    def get_purchase_order(self, po_number: str) -> Dict[str, Any]:
        """Retrieve a purchase order by number.

        Returns a stubbed purchase order with two line items.  The shape of
        the response mirrors what the real API is expected to return, but
        simplified for the MVP.
        """
        return {
            "po_number": po_number,
            "lines": [
                {"description": "Item A", "quantity": 10, "price": 100.00},
                {"description": "Item B", "quantity": 5, "price": 50.00},
            ],
        }

    def post_invoice(self, invoice_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create an invoice in NetSuite.

        Accepts invoice data and returns a stubbed response containing a
        generated NetSuite invoice ID.  No network requests are made.
        """
        invoice_number = invoice_data.get("invoice_number", "UNKNOWN")
        return {"netsuite_invoice_id": f"NS-{invoice_number}"}