"""
Tests for the OCR provider implementation.

These tests exercise the provider selection logic as well as the
behaviour of the GPT‑based provider when OpenAI is unavailable.  When
the environment lacks an API key, ``get_provider`` should return the
fallback provider.  When a key is provided but the OpenAI client
raises an exception, the provider should gracefully fall back to the
stub implementation.  We also verify that a successful call to
``GPTVisionProvider.extract_fields`` parses JSON from the API response.

Note: Rather than hitting the real OpenAI API during testing, we
monkeypatch the ``openai.chat.completions.create`` function to
simulate both error and success scenarios.  This avoids network
dependencies and ensures deterministic tests.
"""

import json
import os

import pytest

from invoice_hawk.ocr_provider import (
    FallbackOCRProvider,
    GPTVisionProvider,
    get_provider,
)


def test_get_provider_fallback_without_api_key(monkeypatch):
    """When no OPENAI_API_KEY is configured, get_provider returns fallback."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("OCR_PROVIDER", "gpt")
    provider = get_provider()
    assert isinstance(provider, FallbackOCRProvider)


def test_get_provider_gpt_with_api_key(monkeypatch):
    """When an API key is provided, get_provider returns GPT provider."""
    monkeypatch.setenv("OPENAI_API_KEY", "dummy-key")
    monkeypatch.setenv("OCR_PROVIDER", "gpt")
    provider = get_provider()
    assert isinstance(provider, GPTVisionProvider)


def test_gpt_provider_fallback_on_error(monkeypatch):
    """The GPT provider falls back to the stub when the API call fails."""
    monkeypatch.setenv("OPENAI_API_KEY", "dummy-key")
    # Monkeypatch the openai client to raise an exception
    import sys
    import types
    # Ensure a dummy openai module exists so monkeypatching works even
    # when the real package is not installed.  We inject a module into
    # sys.modules if necessary.
    if "openai" not in sys.modules:
        dummy = types.ModuleType("openai")
        dummy.chat = types.SimpleNamespace(completions=types.SimpleNamespace())
        sys.modules["openai"] = dummy
    import openai  # type: ignore

    class DummyError(Exception):
        pass

    def fake_create(*args, **kwargs):  # type: ignore[override]
        raise DummyError("simulated failure")

    # Ensure nested attributes exist
    if not hasattr(openai, "chat"):
        openai.chat = types.SimpleNamespace(completions=types.SimpleNamespace())  # type: ignore[attr-defined]
    if not hasattr(openai.chat, "completions"):
        openai.chat.completions = types.SimpleNamespace()  # type: ignore[attr-defined]
    monkeypatch.setattr(openai.chat.completions, "create", fake_create, raising=False)

    provider = GPTVisionProvider(api_key="dummy-key")
    result = provider.extract_fields(b"dummy content")
    # Should be the fallback result
    assert result["vendor"] == "Fallback Vendor"
    assert result["invoice_number"] == "FALLBACK-0001"


def test_gpt_provider_parses_json(monkeypatch):
    """The GPT provider should parse JSON returned by the OpenAI API."""
    monkeypatch.setenv("OPENAI_API_KEY", "dummy-key")
    # Create a fake response object mimicking the OpenAI API structure
    class DummyMessage:
        def __init__(self, content: str) -> None:
            self.content = content

    class DummyChoice:
        def __init__(self, message):
            self.message = message

    class DummyResponse:
        def __init__(self, content: str) -> None:
            self.choices = [DummyChoice(DummyMessage(content))]

    json_payload = {
        "vendor": "Acme Corp",
        "invoice_number": "INV-1001",
        "invoice_date": "2025-07-30",
        "total": 123.45,
        "purchase_order_number": "PO-1234",
        "line_items": [
            {"description": "Widget", "quantity": 10, "price": 12.34},
            {"description": "Gadget", "quantity": 5, "price": 7.89},
        ],
    }
    response_content = json.dumps(json_payload)

    import sys
    import types
    # Ensure a dummy openai module exists if not installed
    if "openai" not in sys.modules:
        dummy = types.ModuleType("openai")
        dummy.chat = types.SimpleNamespace(completions=types.SimpleNamespace())
        sys.modules["openai"] = dummy
    import openai  # type: ignore
    # Ensure nested attributes exist
    if not hasattr(openai, "chat"):
        openai.chat = types.SimpleNamespace(completions=types.SimpleNamespace())  # type: ignore[attr-defined]
    if not hasattr(openai.chat, "completions"):
        openai.chat.completions = types.SimpleNamespace()  # type: ignore[attr-defined]
    # Monkeypatch create to return dummy response
    def fake_create(*args, **kwargs):  # type: ignore[override]
        return DummyResponse(response_content)

    monkeypatch.setattr(openai.chat.completions, "create", fake_create, raising=False)

    provider = GPTVisionProvider(api_key="dummy-key")
    result = provider.extract_fields(b"dummy content")
    assert result == json_payload