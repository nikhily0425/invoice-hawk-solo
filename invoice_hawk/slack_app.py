"""
FastAPI application to handle Slack interactive actions.

This module defines an HTTP endpoint compatible with Slack's interactivity
payloads.  When a user clicks an Approve or Reject button in Slack, Slack
sends a signed request to this endpoint.  The app verifies the request
signature, updates the corresponding invoice status in the database, logs
the action, and optionally posts a follow‑up message to Slack.

To run locally, install ``fastapi`` and ``uvicorn`` (see requirements).
Set ``SLACK_SIGNING_SECRET`` in your environment.  Optional variables
include ``SLACK_BOT_TOKEN`` for updating messages via the Slack Web API.
"""

from __future__ import annotations

import hmac
import hashlib
import json
import os
import time
from typing import Any, Dict

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from .models import Base, Invoice, AuditLog
from .utils import send_slack_message

try:
    # The slack_sdk is optional; we use it only if a bot token is provided.
    from slack_sdk import WebClient  # type: ignore
except Exception:
    WebClient = None  # type: ignore


app = FastAPI()

# Allow CORS during development; in production restrict origins appropriately
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _verify_slack_request(request: Request, body: bytes, signing_secret: str) -> bool:
    """Verify Slack signature according to Slack's signing docs.

    Slack sends two headers: ``X-Slack-Signature`` and ``X-Slack-Request-Timestamp``.
    The signature is computed as ``v0=HMAC_SHA256(signing_secret, 'v0:' + timestamp + ':' + body)``.
    A small tolerance is allowed on the timestamp to prevent replay attacks.
    """
    timestamp = request.headers.get("X-Slack-Request-Timestamp")
    signature = request.headers.get("X-Slack-Signature")
    if not timestamp or not signature:
        return False
    # Reject requests older than 5 minutes
    if abs(time.time() - float(timestamp)) > 60 * 5:
        return False
    basestring = f"v0:{timestamp}:{body.decode()}"
    computed = hmac.new(
        signing_secret.encode(), basestring.encode(), hashlib.sha256
    ).hexdigest()
    expected_sig = f"v0={computed}"
    return hmac.compare_digest(expected_sig, signature)


@app.post("/slack/actions")
async def slack_actions(request: Request) -> JSONResponse:
    """
    Process an interactive action from Slack.

    Slack sends the payload as a form-encoded body with a ``payload``
    parameter containing a JSON string.  We verify the signature, parse
    the payload, update the invoice status, log the action, and optionally
    update the original Slack message.
    """
    signing_secret = os.getenv("SLACK_SIGNING_SECRET")
    if not signing_secret:
        raise HTTPException(status_code=500, detail="SLACK_SIGNING_SECRET not set")
    body = await request.body()
    if not _verify_slack_request(request, body, signing_secret):
        raise HTTPException(status_code=401, detail="Invalid Slack signature")
    # Slack sends a form-urlencoded body; extract the 'payload' parameter
    try:
        form = await request.form()
        payload_json = form.get("payload") or body.decode()
        payload: Dict[str, Any] = json.loads(payload_json)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid payload")
    # Extract the action details
    actions = payload.get("actions", [])
    if not actions:
        return JSONResponse({"error": "No actions"}, status_code=400)
    action = actions[0]
    action_id = action.get("action_id")
    value = action.get("value")
    if not value:
        return JSONResponse({"error": "Missing invoice id"}, status_code=400)
    try:
        invoice_id = int(value)
    except ValueError:
        return JSONResponse({"error": "Invalid invoice id"}, status_code=400)
    # Determine new status based on action
    new_status = "approved" if action_id == "approve_invoice" else "rejected"
    # Connect to DB
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise HTTPException(status_code=500, detail="DATABASE_URL not configured")
    engine = create_engine(db_url)
    Base.metadata.create_all(engine)
    session: Session = Session(engine)
    try:
        invoice = session.get(Invoice, invoice_id)
        if not invoice:
            return JSONResponse({"error": "Invoice not found"}, status_code=404)
        invoice.status = new_status
        # Store the message timestamp and channel if provided
        message_ts = payload.get("message", {}).get("ts")
        channel = payload.get("channel", {}).get("id")
        session.add(
            AuditLog(
                invoice=invoice,
                event_type="slack_action",
                details={
                    "action": action_id,
                    "message_ts": message_ts,
                    "channel": channel,
                },
            )
        )
        session.commit()
    finally:
        session.close()
    # If we have a bot token and message_ts, update the original message via Slack API
    bot_token = os.getenv("SLACK_BOT_TOKEN")
    if bot_token and message_ts and channel and WebClient:
        try:
            client = WebClient(token=bot_token)
            text = f"Invoice {invoice.invoice_number} was {new_status}."
            client.chat_update(channel=channel, ts=message_ts, text=text)
        except Exception:
            # Ignore Slack API errors silently
            pass
    else:
        # Fall back to sending a new message if we cannot update
        webhook = os.getenv("SLACK_WEBHOOK_URL")
        if webhook:
            send_slack_message(webhook, f"Invoice {invoice_id} {new_status}.")
    return JSONResponse({"ok": True})