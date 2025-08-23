"""
Tests for the NetSuite client retry logic.

These tests ensure that the internal `_request` method retries on HTTP
429 responses and succeeds once a non‑429 response is returned.  We use
monkeypatching to simulate different response sequences from
``requests.request`` without making real network calls.
"""

import os

import pytest

from invoice_hawk.netsuite_client import NetSuiteClient, NetSuiteError


class DummyResponse:
    def __init__(self, status_code: int, json_data: dict | None = None, headers: dict | None = None) -> None:
        self.status_code = status_code
        self._json_data = json_data or {}
        self.headers = headers or {}

    def json(self) -> dict:
        return self._json_data

    @property
    def text(self) -> str:  # for error messages
        return str(self._json_data)


def test_retry_on_429(monkeypatch):
    """_request should retry on HTTP 429 and eventually return JSON."""
    # Sequence: first call returns 429, second returns 200
    calls = {"count": 0}
    
    def fake_request(method, url, headers=None, json=None):  # type: ignore[override]
        calls["count"] += 1
        if calls["count"] == 1:
            return DummyResponse(429, headers={"Retry-After": "0"})
        return DummyResponse(200, json_data={"success": True})

    import requests
    monkeypatch.setattr(requests, "request", fake_request)
    os.environ["NETSUITE_BASE_URL"] = "https://example.com"
    os.environ["NETSUITE_MAX_RETRIES"] = "2"
    os.environ["NETSUITE_RETRY_BACKOFF"] = "0"
    ns = NetSuiteClient()
    result = ns._request("GET", "/foo")
    assert result == {"success": True}
    assert calls["count"] == 2


def test_request_raises_on_error(monkeypatch):
    """_request should raise NetSuiteError on non‑429 error responses."""
    def fake_request(method, url, headers=None, json=None):  # type: ignore[override]
        return DummyResponse(500, json_data={"error": "server"})

    import requests
    monkeypatch.setattr(requests, "request", fake_request)
    os.environ["NETSUITE_BASE_URL"] = "https://example.com"
    ns = NetSuiteClient()
    with pytest.raises(NetSuiteError):
        ns._request("GET", "/foo")