#!/usr/bin/env bash
#
# Smoke test script for Invoice Hawk deployment.
#
# This script exercises the deployed OCR and Slack actions endpoints to
# verify that they are reachable and return expected responses.  Set
# the following environment variables before running:
#
#   OCR_URL     – full URL of the /ocr endpoint (e.g. https://abc123.execute-api.us-east-1.amazonaws.com/ocr)
#   SLACK_URL   – full URL of the /slack/actions endpoint
#   SLACK_SECRET – Slack signing secret used in your deployment
#
# You may obtain the API URLs by running `serverless info --stage dev`
# after deployment.  The Slack secret must match the value provided in
# your .env file or AWS parameter store.

set -euo pipefail

if [[ -z "${OCR_URL:-}" ]]; then
  echo "OCR_URL environment variable is not set" >&2
  exit 1
fi
if [[ -z "${SLACK_URL:-}" ]]; then
  echo "SLACK_URL environment variable is not set" >&2
  exit 1
fi
if [[ -z "${SLACK_SECRET:-}" ]]; then
  echo "SLACK_SECRET environment variable is not set" >&2
  exit 1
fi

# A tiny one‑page blank PDF encoded in base64.  See README for details.
PDF_B64="JVBERi0xLjQKMSAwIG9iago8PAovVHlwZSAvQ2F0YWxvZwo+PgplbmRvYmoKMiAwIG9iago8PAovVHlwZSAvUGFnZQovUGFyZW50IDMgMCBSCi9NZWRpYUJveCBbMCAwIDUgN10KPj4KZW5kb2JqCjMgMCBvYmoKPDwKL1R5cGUgL1BhZ2VzCi9LaWRzIFsgMiAwIFIgXQovQ291bnQgMQo+PgplbmRvYmoKeHJlZgowIDQKMDAwMDAwMDAwMCA2NTUzNSBmIAowMDAwMDAwMDExIDAwMDAwIG4gCjAwMDAwMDAwMzAgMDAwMDAgbiAKdHJhaWxlcgo8PAovUm9vdCAxIDAgUgo+PgpzdGFydHhyZWYKMzIKJSVFT0Y="
PAYLOAD=$(printf '{"body":"%s","isBase64Encoded":true}' "$PDF_B64")

echo "Invoking OCR endpoint at $OCR_URL"
OCR_RESPONSE=$(curl -s -X POST "$OCR_URL" -H "Content-Type: application/json" -d "$PAYLOAD") || {
  echo "Error invoking OCR endpoint" >&2; exit 1; }
echo "$OCR_RESPONSE" | grep -q '"vendor"' || { echo "OCR response missing expected fields" >&2; exit 1; }

echo "Invoking Slack actions endpoint at $SLACK_URL"
TIMESTAMP=$(date +%s)
PAYLOAD_JSON='{"actions":[{"action_id":"approve_invoice","value":"1"}],"message":{"ts":"123.123"},"channel":{"id":"C123"}}'
BASESTRING="v0:$TIMESTAMP:$PAYLOAD_JSON"
SIG=$(printf "$BASESTRING" | openssl dgst -sha256 -hmac "$SLACK_SECRET" | sed 's/^.* //')
SLACK_RESP=$(curl -s -X POST "$SLACK_URL" \
  -H "X-Slack-Request-Timestamp: $TIMESTAMP" \
  -H "X-Slack-Signature: v0=$SIG" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  --data-urlencode "payload=$PAYLOAD_JSON") || {
  echo "Error invoking Slack actions endpoint" >&2; exit 1; }
echo "$SLACK_RESP" | grep -q '"ok"' || { echo "Slack actions endpoint did not return ok" >&2; exit 1; }

# Verify invoice post endpoint when URL is provided
if [[ -n "${INVOICE_POST_URL:-}" ]]; then
  echo "Testing invoice post endpoint at $INVOICE_POST_URL"
  POST_RESP=$(curl -s -X POST "$INVOICE_POST_URL" \
    -H "Content-Type: application/json" \
    -d '{"invoice_id": 1}' ) || {
    echo "Error invoking invoice post endpoint" >&2; exit 1; }
  echo "$POST_RESP" | grep -q '"posted"' \
    && echo "Invoice post endpoint reachable." \
    || echo "Invoice post endpoint responded without 'posted' key."
else
  echo "INVOICE_POST_URL not set; skipping invoice post test."
fi

echo "Smoke tests passed."
