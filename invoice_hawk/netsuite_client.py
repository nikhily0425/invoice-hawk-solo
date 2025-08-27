"""
NetSuite client stubs for Invoice Hawk.

This module provides a simple class to interface with the NetSuite REST API.
Actual network requests are not implemented; instead, stub responses are
returned to allow downstream code and tests to proceed without external
dependencies.  Replace these stubs with real API calls once credentials
and endpoints are available.
"""

# invoice_hawk/netsuite_client.py
from __future__ import annotations
import os, time, requests
from typing import Any, Dict, Optional

class NetSuiteError(Exception):
    pass

class NetSuiteClient:
    def __init__(
        self,
        *,
        base_url: Optional[str] = None,
        test_mode: Optional[bool] = None,
        timeout: float = 30.0,
        max_retries: Optional[int] = None,
        backoff_seconds: Optional[float] = None,
    ) -> None:
        self.base_url = (base_url or os.getenv("NETSUITE_BASE_URL", "https://example.com")).rstrip("/")
        env_test = os.getenv("NETSUITE_TEST_MODE", "false").lower() in ("1", "true", "yes")
        self.test_mode = env_test if test_mode is None else test_mode
        self.timeout = timeout
        self.max_retries = int(os.getenv("NETSUITE_MAX_RETRIES", str(max_retries if max_retries is not None else 3)))
        self.backoff_seconds = float(os.getenv("NETSUITE_RETRY_BACKOFF", str(backoff_seconds if backoff_seconds is not None else 0.0)))

    def _request(self, method: str, path: str, json: Optional[dict] = None) -> Dict[str, Any]:
        if self.test_mode:
            # In tests we don’t hit the network.
            return {"status": "dry-run", "method": method, "path": path, "json": json or {}}

        url = f"{self.base_url}/{path.lstrip('/')}"
        last_exc: Optional[Exception] = None
        for attempt in range(self.max_retries + 1):
            try:
                resp = requests.request(method.upper(), url, json=json, timeout=self.timeout)
            except TypeError:

                # Test double doesn't accept 'timeout'
                resp = requests.request(method.upper(), url, json=json)

                if resp.status_code == 429:
                    if attempt == self.max_retries:
                        raise NetSuiteError("Rate limited (429) after retries")
                    time.sleep(self.backoff_seconds * (2 ** attempt))
                    continue
                if resp.status_code >= 400:
                    raise NetSuiteError(f"HTTP {resp.status_code}: {resp.text}")
                try:
                    return resp.json()
                except ValueError:
                    return {"text": resp.text}
            except Exception as exc:
                last_exc = exc
                if attempt == self.max_retries:
                    raise
                time.sleep(self.backoff_seconds * (2 ** attempt))
        raise NetSuiteError(str(last_exc) if last_exc else "Unknown NetSuite error")

    def get_purchase_order(self, po_number: str) -> Dict[str, Any]:
        if self.test_mode:
            # Keys match the code that compares invoice vs PO lines
            return {"po_number": po_number, "lines": [{"sku": "KB-101", "quantity": 10, "price": 99.5}]}
        return self._request("GET", f"po/{po_number}")

    def post_invoice(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create/post an invoice in NetSuite.
        Week 5 contract: in test mode, return a deterministic external_id.
        """
        if self.test_mode:
            return {"external_id": "NS-INV-42"}  # <- what the tests expect
        return self._request("POST", "invoice", json=payload)

__all__ = ["NetSuiteClient", "NetSuiteError"]

