"""
App package for backward compatibility with initial CLI and tests.

The `app` module previously contained standalone scripts for ingest,
matching, OCR, Slack notification, and NetSuite posting. To maintain
compatibility with existing tests (e.g., `tests/test_match.py`), this
package exposes those implementations as importable modules. Newer
implementations reside under the `invoice_hawk` package.

This file marks `app` as a Python package so that `pytest` can import
`app.match_po`. It does not define any runtime logic.
"""

__all__ = ["match_po", "ingest_imap", "ocr_extract", "post_netsuite", "slack_notify"]