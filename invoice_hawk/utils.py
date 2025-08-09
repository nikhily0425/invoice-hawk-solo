"""
Shared utility functions for Invoice Hawk.

This module centralises common operations such as interacting with S3, sending
Slack messages, and loading environment variables.  These helpers abstract away
third‑party libraries so that Lambda handlers remain focused on business logic.
"""

from __future__ import annotations

import os
from typing import Any, Dict, Optional

import boto3
import requests
from botocore.client import BaseClient


def get_s3_client() -> BaseClient:
    """Return an S3 client configured using environment variables or IAM roles."""
    return boto3.client(
        "s3",
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
        region_name=os.getenv("AWS_DEFAULT_REGION", "us-east-1"),
    )


def upload_file_to_s3(
    content: bytes, bucket: str, key: str, *, content_type: str = "application/pdf"
) -> None:
    """Upload binary content to an S3 bucket.

    Parameters
    ----------
    content : bytes
        The raw file bytes.
    bucket : str
        The S3 bucket name.
    key : str
        The object key (path within the bucket).
    content_type : str, optional
        MIME type of the object.  Defaults to application/pdf.
    """
    s3 = get_s3_client()
    s3.put_object(Bucket=bucket, Key=key, Body=content, ContentType=content_type)


def send_slack_message(webhook_url: str, text: str, attachments: Optional[list] = None) -> None:
    """Send a message to Slack via an incoming webhook.

    Slack webhooks expect a JSON payload.  If attachments are provided, they
    should be a list of dicts following Slack’s Block Kit format.
    """
    payload: Dict[str, Any] = {"text": text}
    if attachments:
        payload["attachments"] = attachments
    response = requests.post(webhook_url, json=payload, timeout=10)
    response.raise_for_status()


def query_netsuite_po(po_number: str) -> Dict[str, Any]:
    """Placeholder for NetSuite PO lookup.

    This function should call the NetSuite sandbox REST API to retrieve
    purchase order information by PO number.  The implementation will be
    completed in a later iteration.  Currently it returns a stubbed
    response useful for tests.
    """
    # TODO: implement NetSuite API call (requires authentication)
    # stub response for prototyping purposes
    return {
        "po_number": po_number,
        "lines": [
            {"description": "Item A", "quantity": 10, "price": 100.00},
            {"description": "Item B", "quantity": 5, "price": 50.00},
        ],
    }