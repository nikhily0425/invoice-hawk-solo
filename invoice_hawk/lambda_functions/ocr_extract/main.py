"""
AWS Lambda handler for OCR extraction.

Supports:
1. HTTP API POST /ocr  (JSON: { "pdf_base64": "<base64>" })
2. S3 ObjectCreated event (PDF uploaded to archive bucket)

Performs OCR using the configured provider (GPT or fallback) and returns
extracted invoice JSON. In S3 mode, it does NOT write to DB anymore
(Wk7 moved persistence + posting into separate Lambdas).
"""

import json
import logging
import base64
import os
from typing import Any, Dict

import boto3

from invoice_hawk.ocr_provider import get_provider

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def _download_pdf(bucket: str, key: str) -> bytes:
    """Download PDF from S3 for S3-triggered OCR."""
    s3 = boto3.client("s3")
    obj = s3.get_object(Bucket=bucket, Key=key)
    return obj["Body"].read()


def _http_response(status: int, body: Dict[str, Any]) -> Dict[str, Any]:
    """Return Lambda HTTP API compatible response."""
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }


def handler(event, context):
    """
    Entry point for the OCR Lambda.
    Supports both:
    - HTTP invocation
    - S3 event invocation
    """

    try:
        # 1️⃣ --- HTTP POST /ocr ---
        if "body" in event:
            logger.info("Received HTTP OCR request")

            body_raw = event["body"]
            if event.get("isBase64Encoded"):
                body_raw = base64.b64decode(body_raw).decode()

            try:
                data = json.loads(body_raw)
            except Exception:
                return _http_response(400, {"error": "Invalid JSON body"})

            pdf_b64 = data.get("pdf_base64")
            if not pdf_b64:
                return _http_response(400, {"error": "Missing pdf_base64"})

            try:
                pdf_bytes = base64.b64decode(pdf_b64)
            except Exception:
                return _http_response(400, {"error": "Invalid base64 PDF"})

            provider = get_provider()
            extracted = provider.extract_fields(pdf_bytes)

            return _http_response(200, extracted)

        # 2️⃣ --- S3 Event ---
        if "Records" in event:
            logger.info("Received S3 OCR event")

            record = event["Records"][0]
            bucket = record["s3"]["bucket"]["name"]
            key = record["s3"]["object"]["key"]

            pdf_bytes = _download_pdf(bucket, key)
            provider = get_provider()
            extracted = provider.extract_fields(pdf_bytes)

            # S3-mode does NOT persist (that is handled by later pipeline steps)
            return {
                "status": "ok",
                "source": "s3",
                "vendor": extracted.get("vendor"),
                "invoice_number": extracted.get("invoice_number"),
            }

        # 3️⃣ --- Unsupported event ---
        return _http_response(400, {"error": "Unsupported invocation type"})

    except Exception as e:
        logger.exception("Unexpected OCR handler error: %s", e)
        return _http_response(500, {"error": str(e)})