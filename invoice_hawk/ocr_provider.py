"""
OCR provider pattern for Invoice Hawk.

This module defines a base interface for extracting structured invoice
information from PDF content.  Concrete implementations can call GPT‑4
vision (for production) or use fallback strategies for testing.  The
provider is selected via the `OCR_PROVIDER` environment variable.
"""

from __future__ import annotations

import os
import json
from abc import ABC, abstractmethod
from typing import Any, Dict

import openai


class BaseOCRProvider(ABC):
    """Abstract base class for OCR providers."""

    @abstractmethod
    def extract_fields(self, content: bytes) -> Dict[str, Any]:
        """Extract structured fields from raw PDF bytes."""
        raise NotImplementedError


class GPTVisionProvider(BaseOCRProvider):
    """Use OpenAI’s GPT Vision model to extract invoice fields."""

    def __init__(self, api_key: str) -> None:
        openai.api_key = api_key

    def extract_fields(self, content: bytes) -> Dict[str, Any]:
        # In a real implementation we would send the PDF bytes to OpenAI’s
        # Vision API.  Here we simulate the API call by returning a hard‑coded
        # response.  Replace this stub with an actual call when API access is
        # available.
        # Example prompt (not executed here):
        # response = openai.chat.completions.create(
        #     model="gpt-4o",
        #     messages=[
        #         {"role": "user", "content": [
        #             {"type": "text", "text": "Extract invoice fields (vendor, invoice number, date, total, purchase order number, line items) as JSON."},
        #             {"type": "image", "image": content}
        #         ]}
        #     ],
        #     max_tokens=500,
        # )
        # data = json.loads(response.choices[0].message.content)
        # return data
        return {
            "vendor": "Acme Corp",
            "invoice_number": "INV-1001",
            "invoice_date": "2025-07-01",
            "total": 1500.00,
            "purchase_order_number": "PO-1234",
            "line_items": [
                {"description": "Widget A", "quantity": 10, "price": 50.0},
                {"description": "Widget B", "quantity": 5, "price": 100.0},
            ],
        }


class FallbackOCRProvider(BaseOCRProvider):
    """Fallback parser used for tests and when GPT Vision is unavailable."""

    def extract_fields(self, content: bytes) -> Dict[str, Any]:
        # Without PDF parsing libraries we cannot parse real PDFs here.
        # For testing purposes we return a deterministic payload that
        # downstream code can consume.  Real implementations might use
        # regexes or PDF parsers such as pdfplumber.
        return {
            "vendor": "Fallback Vendor",
            "invoice_number": "FALLBACK-0001",
            "invoice_date": "2025-01-01",
            "total": 100.00,
            "purchase_order_number": "PO-FALLBACK",
            "line_items": [
                {"description": "Fallback Item", "quantity": 1, "price": 100.00},
            ],
        }


def get_provider() -> BaseOCRProvider:
    """Select an OCR provider based on environment variables."""
    provider_name = os.getenv("OCR_PROVIDER", "fallback").lower()
    if provider_name == "gpt":
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY must be set for GPT provider")
        return GPTVisionProvider(api_key)
    return FallbackOCRProvider()