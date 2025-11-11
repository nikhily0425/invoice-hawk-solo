def extract_fields(pdf_path: str) -> dict:
    # TODO: replace with GPT Vision. For now, return a stub.
    return {
        "vendor": "ACME",
        "invoice_no": "INV-123",
        "date": "2025-07-28",
        "total": 995.00,
        "po_number": "45001234",
        "lines": [{"sku": "KB-101", "qty": 10, "unit_price": 99.5}],
    }
