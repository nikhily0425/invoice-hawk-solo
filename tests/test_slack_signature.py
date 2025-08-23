"""
Tests for Slack request signature verification.

We verify that the internal `_verify_slack_request` function accepts
valid signatures and rejects invalid or stale requests.  The function
under test is not exported in the FastAPI app but can be imported
directly for unit testing.
"""

import hmac
import hashlib
import time

from invoice_hawk.slack_app import _verify_slack_request


class DummyRequest:
    def __init__(self, headers: dict) -> None:
        self.headers = headers


def test_verify_slack_signature_valid():
    secret = "mysecret"
    body = b"payload=test"
    timestamp = str(int(time.time()))
    basestring = f"v0:{timestamp}:{body.decode()}"
    sig = hmac.new(secret.encode(), basestring.encode(), hashlib.sha256).hexdigest()
    headers = {
        "X-Slack-Request-Timestamp": timestamp,
        "X-Slack-Signature": f"v0={sig}",
    }
    request = DummyRequest(headers)
    assert _verify_slack_request(request, body, secret) is True


def test_verify_slack_signature_invalid():
    secret = "mysecret"
    body = b"payload=test"
    timestamp = str(int(time.time()))
    headers = {
        "X-Slack-Request-Timestamp": timestamp,
        "X-Slack-Signature": "v0=deadbeef",
    }
    request = DummyRequest(headers)
    assert _verify_slack_request(request, body, secret) is False


def test_verify_slack_signature_old_timestamp():
    """Requests older than 5 minutes should be rejected."""
    secret = "mysecret"
    body = b"payload=test"
    # timestamp 10 minutes in the past
    old_timestamp = str(int(time.time()) - 600)
    basestring = f"v0:{old_timestamp}:{body.decode()}"
    sig = hmac.new(secret.encode(), basestring.encode(), hashlib.sha256).hexdigest()
    headers = {
        "X-Slack-Request-Timestamp": old_timestamp,
        "X-Slack-Signature": f"v0={sig}",
    }
    request = DummyRequest(headers)
    assert _verify_slack_request(request, body, secret) is False