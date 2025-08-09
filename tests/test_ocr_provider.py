from invoice_hawk.ocr_provider import FallbackOCRProvider, GPTVisionProvider


def test_fallback_provider_extracts_stub_fields():
    provider = FallbackOCRProvider()
    result = provider.extract_fields(b"dummy")
    assert result["vendor"] == "Fallback Vendor"
    assert result["invoice_number"] == "FALLBACK-0001"
    assert len(result["line_items"]) == 1


def test_gpt_provider_stub_returns_consistent_fields():
    # Even without a real API key, the GPT provider returns a stubbed response
    provider = GPTVisionProvider(api_key="DUMMY")
    result = provider.extract_fields(b"dummy")
    assert result["vendor"] == "Acme Corp"
    assert result["invoice_number"] == "INV-1001"
    assert len(result["line_items"]) == 2