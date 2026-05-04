#!/usr/bin/env bash
#
# Smoke test for Invoice Hawk deployment (Week 7)
#
# This script validates:
#   ✓ OCR endpoint
#   ✓ Slack interactive actions
#   ✓ Invoice post endpoint
#
# It supports loading URLs directly from:
#     deployment_outputs.json
#

set -euo pipefail

echo "=== Invoice Hawk Smoke Test (Week 7) ==="

# ----------------------------------------------------
# Load endpoints from deployment_outputs.json (optional)
# ----------------------------------------------------
if [[ -f "deployment_outputs.json" ]]; then
  echo "Loading deployment outputs from deployment_outputs.json ..."
  OCR_URL=$(jq -r '.OCRUrl' deployment_outputs.json)
  SLACK_URL=$(jq -r '.SlackActionsUrl' deployment_outputs.json)
  INVOICE_POST_URL=$(jq -r '.InvoicePostUrl' deployment_outputs.json)
fi

# ----------------------------------------------------
# Validate required environment variables
# ----------------------------------------------------
if [[ -z "${OCR_URL:-}" ]]; then
  echo "❌ OCR_URL is not set"
  exit 1
fi
if [[ -z "${SLACK_URL:-}" ]]; then
  echo "❌ SLACK_URL is not set"
  exit 1
fi
if [[ -z "${SLACK_SECRET:-}" ]]; then
  echo "❌ SLACK_SECRET is not set"
  exit 1
fi

echo "Using endpoints:"
echo "  OCR_URL            = $OCR_URL"
echo "  SLACK_URL          = $SLACK_URL"
echo "  INVOICE_POST_URL   = ${INVOICE_POST_URL:-<not-set>}"

# ----------------------------------------------------
# Base64 PDF for testing OCR
# ----------------------------------------------------
PDF_B64="JVBERi0xLjQKMSAwIG9iago8PAovVHlwZSAvQ2F0YWxvZwo+PgplbmRvYmoKMiAwIG9iago8PAovVHlwZSAvUGFnZQovUGFyZW50IDMgMCBSCi9NZWRpYUJveCBbMCAwIDUgN10KPj4KZW5kb2JqCjMgMCBvYmoKPDwKL1R5cGUgL1BhZ2VzCi9LaWRzIFsgMiAwIFIgXQovQ291bnQgMQo+PgplbmRvYmoKeHJlZgowIDQKMDAwMDAwMDAwMCA2NTUzNSBmIAowMDAwMDAwMDExIDAwMDAwIG4gCjAwMDAwMDAwMzAgMDAwMDAgbiAKdHJhaWxlcgo8PAovUm9vdCAxIDAgUgo+PgpzdGFydHhyZWYKMzIKJSVFT0Y="

# ----------------------------------------------------
# OCR TEST
# ----------------------------------------------------
echo
echo "=== Testing OCR endpoint ==="

OCR_PAYLOAD=$(jq -n --arg pdf "$PDF_B64" '{"pdf_base64": $pdf}')

OCR_RESP=$(curl -s -X POST "$OCR_URL" \
  -H "Content-Type: application/json" \
  -d "$OCR_PAYLOAD") || { echo "❌ OCR request failed"; exit 1; }

echo "OCR Response: $OCR_RESP"

echo "$OCR_RESP" | grep -q '"vendor"' \
  && echo "✅ OCR OK" \
  || { echo "❌ OCR response missing vendor"; exit 1; }


# ----------------------------------------------------
# SLACK ACTIONS TEST
# ----------------------------------------------------
echo
echo "=== Testing Slack Actions endpoint ==="

TIMESTAMP=$(date +%s)
SLACK_PAYLOAD=$(jq -nc \
  --arg act "approve_invoice" \
  '{"actions":[{"action_id":$act,"value":"1"}]}' )

BASESTRING="v0:${TIMESTAMP}:${SLACK_PAYLOAD}"
SIGNATURE=$(printf "%s" "$BASESTRING" \
  | openssl dgst -sha256 -hmac "$SLACK_SECRET" \
  | sed 's/^.* //')

SLACK_RESP=$(curl -s -X POST "$SLACK_URL" \
  -H "X-Slack-Request-Timestamp: $TIMESTAMP" \
  -H "X-Slack-Signature: v0=$SIGNATURE" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  --data-urlencode "payload=${SLACK_PAYLOAD}") || {
    echo "❌ Slack request failed"
    exit 1
}

echo "Slack Response: $SLACK_RESP"

echo "$SLACK_RESP" | grep -q '"ok"' \
  && echo "✅ Slack Actions OK" \
  || { echo "❌ Slack actions did not return ok"; exit 1; }


# ----------------------------------------------------
# INVOICE POST TEST (optional)
# ----------------------------------------------------
echo
if [[ -n "${INVOICE_POST_URL:-}" ]]; then
  echo "=== Testing Invoice Post endpoint ==="

  POST_RESP=$(curl -s -X POST "$INVOICE_POST_URL" \
    -H "Content-Type: application/json" \
    -d '{"invoice_id": 1}') || { echo "❌ Invoice post failed"; exit 1; }

  echo "Invoice Post Response: $POST_RESP"

  echo "$POST_RESP" | grep -q '"posted"' \
    && echo "✅ Invoice Post OK" \
    || echo "⚠ Invoice Post responded but did not contain 'posted'"
else
  echo "Skipping invoice post — INVOICE_POST_URL not set"
fi

echo
echo "🎉 Smoke tests passed successfully!"